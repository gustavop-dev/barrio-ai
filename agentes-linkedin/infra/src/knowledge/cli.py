import argparse
import json
from . import agents,db,ingest,providers,retrieval,evaluation

def main():
    parser=argparse.ArgumentParser(description='Biblioteca compartida LinkedIn 01–06')
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ['init','ingest','verify','status']:commands.add_parser(name)
    p=commands.add_parser('embed');p.add_argument('--execute',action='store_true')
    p=commands.add_parser('evaluate');p.add_argument('--mode',choices=['lexical','hybrid'],default='lexical')
    p=commands.add_parser('authorize-retry');p.add_argument('rid');p.add_argument('--reason',required=True)
    p=commands.add_parser('search');p.add_argument('query');p.add_argument('--agent',choices=list(retrieval.AGENTS));p.add_argument('--mode',choices=['lexical','hybrid'],default='lexical')
    p=commands.add_parser('run');p.add_argument('agent',choices=list(retrieval.AGENTS));p.add_argument('task');p.add_argument('--execute',action='store_true');p.add_argument('--mode',choices=['lexical','hybrid'],default='lexical');p.add_argument('--request-id')
    args=vars(parser.parse_args());command=args.pop('command')
    try:
        if command=='init':db.init();result={'initialized':True}
        elif command=='ingest':result=ingest.ingest()
        elif command=='verify':result=ingest.verify()
        elif command=='status':result=db.status()
        elif command=='embed':result=providers.index(**args)
        elif command=='evaluate':result=evaluation.evaluate(**args)
        elif command=='authorize-retry':result=providers.authorize_uncertain_retry(**args)
        elif command=='search':result=retrieval.search(**args)
        else:result=agents.run(**args)
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    except ValueError as exc:
        parser.exit(1,str(exc)+'\n')
