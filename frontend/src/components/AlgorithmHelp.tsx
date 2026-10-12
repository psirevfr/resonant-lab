const methods=[
 {id:'Powell',name:'JeanJacky',scientific:'Powell',how:'Essaie différentes directions de réglage, garde celles qui améliorent le résultat, puis recommence.',limits:'Ne nécessite pas de calcul de pente. Peut demander beaucoup d’essais et rester dans une solution locale.'},
 {id:'L-BFGS-B',name:'Jean Neymar',scientific:'L-BFGS-B',how:'Estime la pente du paysage pour descendre vers une erreur plus faible, en respectant les limites des réglages.',limits:'Adapté à l’affinement lorsque l’erreur varie régulièrement. Peut se bloquer sur un plateau ou une solution locale.'},
 {id:'differential_evolution',name:'Évolution différentielle',scientific:'',how:'Fait évoluer un groupe de montages candidats : elle combine leurs réglages et conserve les meilleurs essais.',limits:'Explore plus largement, mais demande souvent davantage de calculs. Ne garantit pas de trouver la meilleure solution possible.'}
];

export function AlgorithmHelp({method}:{method:string}){
 return <section className="algorithm-help" aria-labelledby="algorithm-help-title">
 <h3 id="algorithm-help-title">Comprendre les algorithmes</h3>
 <div className="algorithm-table-scroll" tabIndex={0} role="region" aria-label="Comparaison des algorithmes, tableau défilable">
 <table><caption>La méthode sélectionnée est mise en évidence.</caption><thead><tr><th scope="col">Méthode</th><th scope="col">Fonctionnement simple</th><th scope="col">Intérêt et limite</th></tr></thead>
 <tbody>{methods.map(m=><tr key={m.id} className={method===m.id?'selected-method':''}><th scope="row"><strong>{m.name}</strong>{m.scientific&&<small>{m.scientific}</small>}{method===m.id&&<span className="algorithm-selected">Sélectionnée</span>}</th><td>{m.how}</td><td>{m.limits}</td></tr>)}</tbody></table>
 </div></section>
}
