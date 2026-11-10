import React,{useState} from 'react';
import {api,ApiError} from './api';
export function PhoneSecurity({mode,onBack}:{mode:'bind'|'reset',onBack:()=>void}){
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(''),[sentAt,setSentAt]=useState(0);
 async function perform(form:HTMLFormElement,sending:boolean){
  if(!form.reportValidity())return;
  const f=new FormData(form),username=String(f.get('username')),phone=String(f.get('phone'));
  setBusy(true);setError('');setMessage('');let authenticated=false;
  try{
   if(mode==='bind'){await api('/auth/login','POST',{username,password:f.get('password')});authenticated=true;}
   if(sending){
    if(Date.now()-sentAt<60000)throw new Error('请等待60秒后再发送');
    await api(mode==='bind'?'/auth/phone/send':'/auth/phone/reset/send','POST',{username,phone});
    setSentAt(Date.now());setMessage('验证码已发送，5分钟内有效。');
   }else{
    await api(mode==='bind'?'/auth/phone/bind':'/auth/phone/reset','POST',{username,phone,code:f.get('code'),new_password:f.get('new_password'),confirm_password:f.get('confirm_password')});
    form.reset();setMessage(mode==='bind'?'手机号绑定成功，请返回登录。':'密码已更新，请返回登录。');
   }
  }catch(e){setError(e instanceof ApiError&&e.status===404?'当前后端尚未加载手机验证接口，需要完成数据库迁移并重启服务。':e instanceof Error?e.message:'操作失败');}
  finally{if(authenticated)await api('/auth/logout','POST').catch(()=>{});setBusy(false);}
 }
 return <><h2>{mode==='bind'?'绑定手机号':'短信验证修改密码'}</h2><p className="muted">{mode==='bind'?'先验证账号和当前密码，再通过短信确认手机号归属。':'使用已绑定的手机号验证身份后设置新密码。'}</p>{error&&<div role="alert" className="error">{error}</div>}{message&&<div role="status" className="notice">{message}</div>}<form onSubmit={e=>{e.preventDefault();void perform(e.currentTarget,false)}}><fieldset disabled={busy} style={{border:0,padding:0,margin:0}}><label className="field">账号<input name="username" required autoComplete="username" maxLength={80}/></label>{mode==='bind'&&<label className="field">当前密码<input name="password" type="password" required autoComplete="current-password" maxLength={128}/></label>}<label className="field">手机号<input name="phone" type="tel" inputMode="tel" pattern="1[3-9][0-9]{9}" required maxLength={11} autoComplete="tel"/></label><button type="button" onClick={e=>{const form=e.currentTarget.form!;const phone=form.elements.namedItem('phone') as HTMLInputElement;const username=form.elements.namedItem('username') as HTMLInputElement;const password=form.elements.namedItem('password') as HTMLInputElement|null;if(username.reportValidity()&&phone.reportValidity()&&(!password||password.reportValidity())){void performSend(form)}}}>发送短信验证码</button><label className="field">短信验证码<input name="code" inputMode="numeric" pattern="[0-9]{6}" required maxLength={6} autoComplete="one-time-code"/></label>{mode==='reset'&&<><label className="field">新密码（10至128位）<input name="new_password" type="password" required minLength={10} maxLength={128} autoComplete="new-password"/></label><label className="field">确认新密码<input name="confirm_password" type="password" required minLength={10} maxLength={128} autoComplete="new-password"/></label></>}<button className="primary">{busy?'正在处理…':mode==='bind'?'确认绑定手机号':'确认修改密码'}</button></fieldset></form><p className="footnote">短信服务需配置后才能实际发送。没有绑定手机号且忘记密码时，请联系管理员。</p><button disabled={busy} onClick={onBack}>返回</button></>;
 async function performSend(form:HTMLFormElement){
  const fields=Array.from(form.querySelectorAll<HTMLInputElement>('input')).filter(x=>['code','new_password','confirm_password'].includes(x.name));
  fields.forEach(x=>x.required=false);
  try{await perform(form,true);}finally{fields.forEach(x=>x.required=true);}
 }
}
