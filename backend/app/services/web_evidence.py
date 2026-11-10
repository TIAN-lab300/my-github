"""Public-web evidence retrieval with pinned DNS, bounded redirects and payloads."""
import http.client
import ipaddress
import json
import os
import socket
import ssl
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin,urlunsplit
import httpx


def public_target(url):
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('网址必须为无凭据的HTTP或HTTPS地址')
    if parsed.port not in (None,80 if parsed.scheme=='http' else 443):
        raise ValueError('只支持公共网页标准端口')
    addresses=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)
    ips=[address[4][0] for address in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError('不允许访问本地、私有或特殊网络地址')
    return parsed,ips[0]


class PageText(HTMLParser):
    def __init__(self):
        super().__init__();self.hidden=0;self.title=False;self.titles=[];self.parts=[];self.published_at=None

    def handle_starttag(self,tag,attrs):
        attributes=dict(attrs)
        if tag=='meta' and (attributes.get('property') or attributes.get('name') or attributes.get('itemprop') or '').lower() in ('article:published_time','datepublished','date'):
            try:self.published_at=datetime.fromisoformat((attributes.get('content') or '').replace('Z','+00:00')).isoformat()
            except ValueError:pass
        if tag in ('script','style','noscript','template'):self.hidden+=1
        if tag=='title':self.title=True

    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','template'):self.hidden=max(0,self.hidden-1)
        if tag=='title':self.title=False

    def handle_data(self,data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())
            if self.title:self.titles.append(data.strip())


def fetch_page(url):
    for redirect in range(4):
        parsed,address=public_target(url)
        port=parsed.port or (443 if parsed.scheme=='https' else 80)
        connection=http.client.HTTPConnection(address,port,timeout=10)
        connection.connect()
        if parsed.scheme=='https':
            connection.sock=ssl.create_default_context().wrap_socket(connection.sock,server_hostname=parsed.hostname)
        try:
            target=urlunsplit(('', '',parsed.path or '/',parsed.query,''))
            connection.request('GET',target,headers={'Host':parsed.hostname,'User-Agent':'ZhixingCourseImporter/1.0','Accept-Encoding':'identity','Accept':'text/html,text/plain'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ValueError('网页重定向缺少目标')
                url=urljoin(url,location)
                continue
            if response.status!=200:raise ValueError('网页不可访问，HTTP '+str(response.status))
            mime=response.getheader('Content-Type','').split(';')[0].strip().lower()
            if mime not in ('text/html','text/plain','application/xhtml+xml'):raise ValueError('当前仅支持网页和纯文本正文')
            if response.getheader('Content-Encoding','identity')!='identity':raise ValueError('不支持压缩网页响应')
            deadline=time.monotonic()+20
            parts=[];size=0
            while size<=2*1024*1024:
                if time.monotonic()>deadline:raise ValueError('网页读取超过时间限制')
                part=response.read1(65536)
                if not part:break
                parts.append(part);size+=len(part)
            data=b''.join(parts)
            if len(data)>2*1024*1024:raise ValueError('网页正文超过2MiB限制')
            charset=response.headers.get_content_charset() or 'utf-8'
            text=data.decode(charset,errors='replace')
            page=PageText()
            if mime=='text/plain':body=text;title=parsed.hostname
            else:
                page.feed(text);body='\n'.join(page.parts);title=' '.join(page.titles) or parsed.hostname
            if len(body.strip())<30:raise ValueError('网页没有足够正文，可能需要登录或动态加载')
            return {'url':url,'title':title[:300],'body':body,'domain':parsed.hostname,'published_at':page.published_at}
        finally:
            connection.close()
    raise ValueError('网页重定向次数超过限制')


def search_status():
    provider=os.getenv('ZHIXING_SEARCH_PROVIDER','tavily')
    key_name='DASHSCOPE_API_KEY' if provider=='dashscope' else 'TAVILY_API_KEY'
    return {'provider':provider,'configured':bool(os.getenv(key_name)) and provider in ('tavily','dashscope')}


def search_web(query):
    status=search_status()
    if not status['configured']:raise ValueError('实时搜索尚未配置，请联系管理员配置搜索服务')
    with httpx.Client(timeout=15,follow_redirects=False) as client:
        if status['provider']=='dashscope':
            response=client.post('https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                headers={'Authorization':'Bearer '+os.environ['DASHSCOPE_API_KEY']},
                json={'model':os.getenv('ZHIXING_SEARCH_MODEL','qwen-plus'),'input':{'messages':[{'role':'user','content':query}]},
                      'parameters':{'enable_search':True,'result_format':'message','search_options':{'forced_search':True,'enable_source':True}}})
            if response.status_code!=200:raise ValueError('搜索服务响应异常，HTTP '+str(response.status_code))
            info=response.json().get('output',{}).get('search_info')
            if not isinstance(info,dict) or not isinstance(info.get('search_results'),list):raise ValueError('供应商未返回真实搜索来源，不能将模型回答当作联网结果')
            raw=info['search_results']
        else:
            response=client.post('https://api.tavily.com/search',json={'api_key':os.environ['TAVILY_API_KEY'],'query':query,'max_results':5,'search_depth':'basic','include_raw_content':False})
            if response.status_code!=200:raise ValueError('搜索服务响应异常，HTTP '+str(response.status_code))
            raw=response.json().get('results')
    if not isinstance(raw,list):raise ValueError('搜索服务返回格式异常')
    candidates=[];seen=set()
    for item in raw[:5]:
        if not isinstance(item,dict):continue
        url=item.get('url','')
        if not isinstance(url,str):continue
        try:parsed,_=public_target(url)
        except (ValueError,OSError):continue
        canonical=urlunsplit((parsed.scheme,parsed.netloc,parsed.path.rstrip('/') or '/',parsed.query,''))
        if canonical in seen:continue
        seen.add(canonical)
        candidates.append({'url':canonical,'title':str(item.get('title',''))[:300],
                           'domain':parsed.hostname,'reason':str(item.get('content') or item.get('snippet') or '本次搜索返回的来源网址，正文需教师核实')[:1000],
                           'status':'unverified','published_at':None,'provider':status['provider']})
    return candidates
