import type {ReactNode} from 'react';
import {useSiteLayout} from './siteLayout';

export default function SiteElementText({id,children}:{id:string;children:ReactNode}){
 return useSiteLayout().elements?.[id]?.text??children;
}
