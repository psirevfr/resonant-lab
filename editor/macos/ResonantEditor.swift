import AppKit
import WebKit
import Security
import Darwin

private final class NoRedirects: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

@MainActor
final class EditorDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var overlay: NSView!
    private var status: NSTextField!
    private var spinner: NSProgressIndicator!
    private var retry: NSButton!
    private var backend: Process?
    private var output = Data()
    private var token = ""
    private var editorURL: URL?
    private var startupTimer: Timer?
    private var quitting = false
    private var checkingQuit = false
    private var signals: [DispatchSourceSignal] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        installMenus()
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 760), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Résonant — Éditeur"
        window.minSize = NSSize(width: 960, height: 700)
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .darkAqua)
        window.center()
        window.setFrameAutosaveName("ResonantEditorWindow")
        let content = NSView(frame: window.contentView!.bounds)
        content.autoresizingMask = [.width, .height]
        window.contentView = content
        webView.frame = content.bounds
        content.addSubview(webView)
        makeOverlay(in: content)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        installSignals()
        startBackend()
    }

    private func makeOverlay(in content: NSView) {
        overlay = NSView(frame: content.bounds)
        overlay.autoresizingMask = [.width, .height]
        overlay.wantsLayer = true
        overlay.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        content.addSubview(overlay)
        spinner = NSProgressIndicator()
        spinner.style = .spinning
        spinner.controlSize = .regular
        status = NSTextField(wrappingLabelWithString: "Ouverture de votre éditeur local…")
        status.font = .systemFont(ofSize: 17)
        status.alignment = .center
        status.setContentHuggingPriority(.defaultLow, for: .horizontal)
        retry = NSButton(title: "Réessayer", target: self, action: #selector(retryStartup))
        retry.isHidden = true
        let stack = NSStackView(views: [spinner, status, retry])
        stack.orientation = .vertical
        stack.spacing = 20
        stack.translatesAutoresizingMaskIntoConstraints = false
        overlay.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: overlay.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: overlay.centerYAnchor),
            stack.widthAnchor.constraint(lessThanOrEqualToConstant: 600),
            stack.leadingAnchor.constraint(greaterThanOrEqualTo: overlay.leadingAnchor, constant: 32)
        ])
    }

    private func installMenus() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(withTitle: "À propos de Résonant Éditeur", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quitter Résonant Éditeur", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let editItem = NSMenuItem()
        main.addItem(editItem)
        let edit = NSMenu(title: "Édition")
        editItem.submenu = edit
        edit.addItem(withTitle: "Annuler", action: Selector(("undo:")), keyEquivalent: "z")
        let redo = edit.addItem(withTitle: "Rétablir", action: Selector(("redo:")), keyEquivalent: "z")
        redo.keyEquivalentModifierMask = [.command, .shift]
        edit.addItem(.separator())
        edit.addItem(withTitle: "Couper", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copier", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Coller", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Tout sélectionner", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        let viewItem = NSMenuItem()
        main.addItem(viewItem)
        let view = NSMenu(title: "Affichage")
        viewItem.submenu = view
        view.addItem(withTitle: "Recharger l’éditeur", action: #selector(reloadEditor), keyEquivalent: "r").target = self
        NSApp.mainMenu = main
    }

    private func installSignals() {
        for value in [SIGTERM, SIGINT] {
            signal(value, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: value, queue: .main)
            source.setEventHandler { NSApp.terminate(nil) }
            source.resume()
            signals.append(source)
        }
    }

    private func showStatus(_ message: String, failed: Bool = false) {
        overlay.isHidden = false
        status.stringValue = message
        retry.isHidden = !failed
        if failed { spinner.stopAnimation(nil) } else { spinner.startAnimation(nil) }
    }

    @objc private func retryStartup() { startBackend() }

    private func startBackend() {
        stopBackend()
        editorURL = nil
        output.removeAll(keepingCapacity: false)
        showStatus("Ouverture de votre éditeur local…")
        guard let repo = Bundle.main.object(forInfoDictionaryKey: "ResonantRepositoryPath") as? String,
              repo.hasPrefix("/") else {
            showStatus("Le dossier du projet est introuvable. Reconstruisez l’application depuis votre dépôt.", failed: true)
            return
        }
        let root = URL(fileURLWithPath: repo, isDirectory: true)
        let python = root.appendingPathComponent(".venv/bin/python")
        let server = root.appendingPathComponent("editor/server.py")
        guard FileManager.default.isExecutableFile(atPath: python.path),
              FileManager.default.fileExists(atPath: server.path) else {
            showStatus("L’éditeur n’est pas installé dans ce dossier. Vérifiez l’environnement Python puis reconstruisez l’application.", failed: true)
            return
        }
        var random = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, random.count, &random) == errSecSuccess else {
            showStatus("Impossible de préparer une session locale sécurisée. Réessayez.", failed: true)
            return
        }
        token = random.map { String(format: "%02x", $0) }.joined()
        let process = Process()
        process.executableURL = python
        process.arguments = [server.path, "--repo", root.path, "--port", "0"]
        process.currentDirectoryURL = root
        var environment = ProcessInfo.processInfo.environment
        environment["RESONANT_EDITOR_TOKEN"] = token
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr
        stdout.fileHandleForReading.readabilityHandler = { [weak self, weak process] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            DispatchQueue.main.async { [weak self, weak process] in
                guard let self, let process, self.backend === process else { return }
                self.receive(data)
            }
        }
        // Drain diagnostics without displaying or logging paths, tokens or raw
        // application output. The server provides public errors in its own UI.
        stderr.fileHandleForReading.readabilityHandler = { handle in
            if handle.availableData.isEmpty { handle.readabilityHandler = nil }
        }
        process.terminationHandler = { [weak self, weak process] _ in
            DispatchQueue.main.async { [weak self, weak process] in
                guard let self, let process, self.backend === process, !self.quitting else { return }
                self.startupTimer?.invalidate()
                self.showStatus("Le moteur local s’est arrêté. Vous pouvez le relancer sans mettre le site en ligne.", failed: true)
            }
        }
        backend = process
        do { try process.run() }
        catch {
            backend = nil
            stdout.fileHandleForReading.readabilityHandler = nil
            stderr.fileHandleForReading.readabilityHandler = nil
            showStatus("Le moteur local n’a pas pu démarrer. Vérifiez l’installation du projet.", failed: true)
            return
        }
        startupTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: false) { [weak self, weak process] _ in
            DispatchQueue.main.async { [weak self, weak process] in
                guard let self, let process, self.backend === process, self.editorURL == nil else { return }
                self.stopBackend()
                self.showStatus("L’ouverture prend trop de temps. Vérifiez l’installation puis réessayez.", failed: true)
            }
        }
    }

    private func receive(_ data: Data) {
        guard editorURL == nil else { return }
        output.append(data)
        guard output.count <= 65_536 else {
            stopBackend()
            showStatus("Le moteur local a envoyé une réponse inattendue.", failed: true)
            return
        }
        while let newline = output.firstIndex(of: 10) {
            let line = output.prefix(upTo: newline)
            output.removeSubrange(...newline)
            guard let object = try? JSONSerialization.jsonObject(with: line) as? [String: Any],
                  object["ready"] as? Bool == true,
                  let value = object["url"] as? String,
                  let url = URL(string: value),
                  url.scheme == "http", url.host == "127.0.0.1",
                  let port = url.port, (1...65535).contains(port),
                  url.user == nil, url.password == nil, url.query == nil, url.fragment == nil else { continue }
            editorURL = url
            startupTimer?.invalidate()
            reloadEditor()
            return
        }
    }

    @objc private func reloadEditor() {
        guard let url = editorURL else { return }
        var request = URLRequest(url: url)
        request.setValue(token, forHTTPHeaderField: "X-Editor-Token")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        webView.load(request)
    }

    private func internalURL(_ url: URL) -> Bool {
        guard let base = editorURL else { return false }
        return url.scheme == "http" && url.host == "127.0.0.1" && url.port == base.port && url.user == nil && url.password == nil
    }

    private func fetchState(_ completion: @escaping @MainActor ([String: Any]?) -> Void) {
        guard let base = editorURL else { completion(nil); return }
        var request = URLRequest(url: base.appendingPathComponent("api/state"))
        request.setValue(token, forHTTPHeaderField: "X-Editor-Token")
        request.timeoutInterval = 3
        let session = URLSession(configuration: .ephemeral, delegate: NoRedirects(), delegateQueue: nil)
        session.dataTask(with: request) { data, response, _ in
            var state: [String: Any]?
            if let response = response as? HTTPURLResponse, response.statusCode == 200,
               let data, data.count <= 1_048_576 {
                state = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            }
            session.finishTasksAndInvalidate()
            let result = state
            DispatchQueue.main.async { completion(result) }
        }.resume()
    }

    private func permitPreview(_ action: WKNavigationAction, decision: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let target = action.request.url,
              action.targetFrame?.isMainFrame == false,
              target.scheme == "http", target.host == "127.0.0.1", target.port != nil,
              target.user == nil, target.password == nil,
              action.request.value(forHTTPHeaderField: "X-Editor-Token") == nil else { decision(.cancel); return }
        // An iframe may reach only the preview port announced by our own
        // authenticated backend, never an arbitrary localhost application.
        fetchState { state in
            var allowed = false
            if let state,
               let value = state["previewUrl"] as? String, let preview = URL(string: value) {
                allowed = preview.scheme == "http" && preview.host == "127.0.0.1" && preview.port == target.port && preview.user == nil && preview.password == nil
            }
            decision(allowed ? .allow : .cancel)
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if internalURL(url) {
            if navigationAction.targetFrame == nil {
                if navigationAction.navigationType == .linkActivated { webView.load(navigationAction.request) }
                decisionHandler(.cancel)
            } else { decisionHandler(.allow) }
        } else if url.absoluteString == "about:blank" && navigationAction.targetFrame?.isMainFrame == false {
            decisionHandler(.allow)
        } else if url.scheme == "http" && url.host == "127.0.0.1" && navigationAction.targetFrame?.isMainFrame == false {
            permitPreview(navigationAction, decision: decisionHandler)
        } else {
            // Only an actual clicked HTTPS link may leave the editor. Scripted
            // redirects and popups cannot trigger an external application.
            if navigationAction.navigationType == .linkActivated && url.scheme == "https" {
                NSWorkspace.shared.open(url)
            }
            decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? { nil }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { overlay.isHidden = true }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { navigationFailed(error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { navigationFailed(error) }

    private func navigationFailed(_ error: Error) {
        if (error as NSError).code != NSURLErrorCancelled && !quitting {
            showStatus("L’interface locale ne répond pas. Réessayez pour relancer l’éditeur.", failed: true)
        }
    }

    private func stopBackend() {
        startupTimer?.invalidate()
        guard let process = backend else { return }
        backend = nil
        if process.isRunning {
            process.terminate()
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let process = backend, process.isRunning else { return .terminateNow }
        if checkingQuit { return .terminateLater }
        checkingQuit = true
        let previousOverlay = overlay.isHidden
        showStatus("Vérification de l’activité en cours…")
        window.makeFirstResponder(nil)
        fetchState { [weak self, weak process] state in
            guard let self, let process else { NSApp.reply(toApplicationShouldTerminate: true); return }
            let job = state?["job"] as? [String: Any]
            let jobStatus = (job?["status"] as? String ?? "").lowercased()
            let active = ["queued", "running", "preparing", "publishing", "préparation", "publication"].contains(jobStatus)
            if state == nil || active {
                let alert = NSAlert()
                alert.alertStyle = .warning
                alert.messageText = active ? "Une opération est encore en cours" : "Impossible de vérifier l’activité du projet"
                alert.informativeText = active ? "Fermer maintenant peut interrompre la préparation ou la publication. Vous pouvez laisser l’éditeur ouvert jusqu’à la fin." : "Une opération pourrait être en cours. Laissez l’éditeur ouvert si vous venez de lancer une préparation ou une publication."
                alert.addButton(withTitle: "Laisser ouvert")
                alert.addButton(withTitle: "Quitter quand même")
                alert.beginSheetModal(for: self.window) { [weak self, weak process] response in
                    guard let self else { NSApp.reply(toApplicationShouldTerminate: true); return }
                    if response == .alertFirstButtonReturn {
                        self.checkingQuit = false
                        self.overlay.isHidden = previousOverlay
                        NSApp.reply(toApplicationShouldTerminate: false)
                    } else if let process { self.finishQuit(process) }
                    else { NSApp.reply(toApplicationShouldTerminate: true) }
                }
            } else { self.finishQuit(process) }
        }
        return .terminateLater
    }

    private func finishQuit(_ process: Process) {
        quitting = true
        startupTimer?.invalidate()
        if process.isRunning { process.terminate() }
        let deadline = Date().addingTimeInterval(3)
        Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { timer in
            if !process.isRunning || Date() >= deadline {
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
                timer.invalidate()
                NSApp.reply(toApplicationShouldTerminate: true)
            }
        }
    }

    func applicationWillTerminate(_ notification: Notification) { stopBackend() }
}

@main
enum ResonantEditorMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        let delegate = EditorDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
        withExtendedLifetime(delegate) {}
    }
}
