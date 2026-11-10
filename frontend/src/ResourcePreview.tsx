import {useRef, useState} from 'react';

export function ResourcePreview({resource}: {resource: any}) {
  const media = useRef<HTMLMediaElement | null>(null);
  const [message, setMessage] = useState('');
  const source = `/api/v1/resources/${resource.id}/download?inline=true`;
  const timed = resource.body?.includes('【时间 ');
  const segments = timed ? resource.body.split(/(?=【时间 )/) : [];

  function seek(seconds: number) {
    const player = media.current;
    if (!player || player.readyState === 0) {
      setMessage('请先加载音视频，再定位字幕时间。');
      return;
    }
    if (Number.isFinite(player.duration) && seconds > player.duration) {
      setMessage('字幕时间超出媒体长度，请联系资料上传者校正。');
      return;
    }
    player.currentTime = seconds;
    setMessage('已定位，请点击播放。');
  }

  return <>
    {resource.kind === 'video' && <video ref={element=>{media.current=element}} controls onError={()=>setMessage('当前浏览器无法播放，请下载原文件或转码后重新上传。')} style={{width: '100%', maxHeight: 400}} src={source}/>}
    {resource.kind === 'audio' && <audio ref={element=>{media.current=element}} controls onError={()=>setMessage('当前浏览器无法播放，请下载原文件或转码后重新上传。')} src={source}/>}
    {resource.kind === 'image' && <img style={{maxWidth: '100%'}} src={source} alt={resource.title}/>}
    {resource.mime === 'application/pdf' && <iframe title={resource.title} src={source} style={{width: '100%', height: 600}}/>}
    {message && <p role="status">{message}</p>}
    {timed ? segments.map((segment: string, index: number) => {
      const time = segment.match(/^【时间 ([\d.]+)–([\d.]+) 秒】/);
      return <div key={index} className="listrow">
        {time && ['video', 'audio'].includes(resource.kind) && <button onClick={() => seek(Number(time[1]))}>定位到 {time[1]} 秒</button>}
        <article className="reading">{segment}</article>
      </div>;
    }) : resource.body && <article className="reading">{resource.body}</article>}
  </>;
}
