import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('host_security',Path(__file__).resolve().parents[2]/'scripts/check_host_security.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


def test_inventory_flags_php_without_disclosing_configuration(monkeypatch):
    def command(args):
        return {'status':'ok','output':{
            'dpkg-query':'php8.1-fpm\t8.1.2-ubuntu-security\tinstalled\nnginx\t1.18.0-ubuntu-security\tinstalled\nother\t1\tinstalled\n',
            'php':'PHP 8.1.2 (cli)',
            'systemctl':'php8.1-fpm.service loaded active running PHP\nnginx.service loaded active running nginx\n',
            'nginx':'fastcgi_pass unix:/run/php/php8.1-fpm.sock;\n# secret_value_do_not_print\nclient_max_body_size 128m;\nlimit_req zone=login;'
        }[args[0]]}
    monkeypatch.setattr(host,'command',command)
    result=host.inventory(True)
    assert result['php_review_required']
    assert result['nginx']['php_or_fastcgi_present']
    assert result['nginx']['rate_limiting_present']
    assert len(result['packages'])==2
    assert 'secret_value_do_not_print' not in str(result) and 'php8.1-fpm.sock' not in str(result)


def test_missing_access_is_not_reported_as_a_successful_check(monkeypatch):
    monkeypatch.setattr(host,'command',lambda _: {'status':'not_checked','output':'private diagnostic text'})
    result=host.inventory(True)
    assert result['nginx']=={'status':'not_checked'}
    assert result['packages_status']=='not_checked'
    assert result['php_review_required'] is None
    assert 'private diagnostic text' not in str(result)
