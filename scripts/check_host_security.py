#!/usr/bin/env python3
"""Read-only host inventory. Run ON THE VM; never reads environment/secrets.

No exploit, update, restart, or configuration change. JSON contains only selected
versions/counts, never raw nginx configuration or process command lines.
"""
import argparse
import json
import re
import shutil
import subprocess


def command(args):
    if shutil.which(args[0]) is None:return {'status':'unavailable','output':''}
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=15)
        return {'status':'ok' if result.returncode==0 else 'not_checked','output':result.stdout+result.stderr}
    except (OSError,subprocess.TimeoutExpired):return {'status':'not_checked','output':''}


def inventory(include_nginx=False):
    packages=command(['dpkg-query','-W','-f=${Package}\t${Version}\t${db:Status-Status}\n'])
    selected=[]
    for line in packages['output'].splitlines():
        parts=line.split('\t')
        if len(parts)==3 and parts[2]=='installed' and re.fullmatch(r'(?:php[\w.+:-]*|nginx[\w.+:-]*|openssl|openssh-server|ca-certificates)',parts[0]):
            selected.append({'package':parts[0],'version':parts[1]})
    php=command(['php','--version']);match=re.search(r'PHP (\d+\.\d+\.\d+)',php['output'])
    services=command(['systemctl','list-units','--all','--type=service','--no-legend','--plain','--no-pager'])
    relevant=[]
    for line in services['output'].splitlines():
        parts=line.split()
        if len(parts)>=4 and re.fullmatch(r'(?:php[^/]*-fpm|apache2|nginx|resonant[^/]*)\.service',parts[0]):
            relevant.append({'unit':parts[0],'load':parts[1],'active':parts[2],'sub':parts[3]})
    nginx={'status':'not_requested'}
    if include_nginx:
        result=command(['nginx','-T'])
        # A failed permissions/configuration check cannot establish exposure.
        nginx={'status':result['status']}
        if result['status']=='ok':
            directives='\n'.join(l.split('#',1)[0] for l in result['output'].splitlines())
            nginx.update({'php_or_fastcgi_present':bool(re.search(r'fastcgi_pass|\.php',directives,re.I)),
                          'rate_limiting_present':bool(re.search(r'\blimit_req\s',directives)),
                          'body_limit_present':bool(re.search(r'\bclient_max_body_size\s',directives))})
    php_present=bool(match or any(p['package'].startswith('php') for p in selected) or any(s['unit'].startswith('php') for s in relevant) or nginx.get('php_or_fastcgi_present'))
    return {'scope':'this_host_only','packages_status':packages['status'],'packages':selected,
            'php_cli_status':php['status'],'php_cli_version':match[1] if match else None,
            'services_status':services['status'],'services':relevant,'nginx':nginx,
            'php_review_required':True if php_present else False if packages['status']=='ok' and services['status']=='ok' and nginx['status']=='ok' else None,
            'note':'Absence in this inventory does not exclude PHP in containers or other virtual hosts. Vendor backports must be checked before judging a package version.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nginx',action='store_true',help='Inspect nginx -T privately; usually requires sudo. Raw configuration is never printed.')
    args=parser.parse_args()
    print(json.dumps(inventory(args.nginx),indent=2,ensure_ascii=False))
