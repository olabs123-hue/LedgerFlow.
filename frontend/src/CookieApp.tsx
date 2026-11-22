import {useCallback, useEffect, useState} from 'react';
import {Activity, ArrowRight, ArrowUpRight, Database, LockKeyhole, LogOut, ShieldCheck, Wallet} from 'lucide-react';

/**
 * Opt-in same-origin browser client.
 * All requests use relative /browser routes so credentials never cross origins.
 * Session JWT is carried in an HttpOnly cookie, never read by JavaScript.
 */
type Profile = {email:string;balance_cents:number;account_id:number;simulation:boolean};
type Transfer = {id:number;direction:'sent'|'received';amount_cents:number;created_at:string};
type Session = {authenticated:true;csrf_token:string};
type TransferResult = {transfer_id:number;replayed:boolean};
const formatMoney=(c:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(c/100);

async function browserCall<T>(path:string, method='GET', body?:unknown, csrf?:string, key?:string):Promise<T>{
  const response = await fetch('/browser'+path,{
    method,
    credentials:'same-origin',
    cache:'no-store',
    headers:{
      ...(body!==undefined?{'Content-Type':'application/json'}:{}),
      ...(csrf?{'X-CSRF-Token':csrf}:{}),
      ...(key?{'Idempotency-Key':key}:{}),
    },
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if(!response.ok){
    const payload=await response.json().catch(()=>({detail:'Request failed'}));
    throw new Error(typeof payload.detail==='string'?payload.detail:'Request failed');
  }
  return response.json() as Promise<T>;
}

export default function CookieApp(){
  const [csrf,setCsrf]=useState('');
  const [profile,setProfile]=useState<Profile|null>(null);
  const [history,setHistory]=useState<Transfer[]>([]);
  const [email,setEmail]=useState('');
  const [password,setPassword]=useState('');
  const [recipient,setRecipient]=useState('');
  const [amount,setAmount]=useState('');
  const [loading,setLoading]=useState(false);
  const [status,setStatus]=useState('Checking your browser session…');
  const [error,setError]=useState('');

  const refresh=useCallback(async()=>{
    const [me,items]=await Promise.all([
      browserCall<Profile>('/me'),
      browserCall<Transfer[]>('/transfers')
    ]);
    setProfile(me);
    setHistory(items);
  },[]);

  useEffect(()=>{
    let active=true;
    void browserCall<Session>('/session').then(async session=>{
      if(!active)return;
      setCsrf(session.csrf_token);
      await refresh();
      if(active)setStatus('');
    }).catch(()=>{
      if(active){setCsrf('');setProfile(null);setStatus('Sign in using a demo account.');}
    });
    return ()=>{active=false;};
  },[refresh]);

  async function signIn(e:React.FormEvent){
    e.preventDefault();setLoading(true);setError('');
    try{
      const result=await browserCall<Session>('/session','POST',{email,password});
      setPassword('');
      setCsrf(result.csrf_token);
      await refresh();
      setStatus('');
    }catch(e){setError((e as Error).message);}finally{setLoading(false);}
  }

  async function signOut(){
    setLoading(true);setError('');
    try{
      await browserCall<{message:string}>('/logout','POST',undefined,csrf);
    }catch{
      setError('The server could not confirm session revocation. Close this browser and contact the demo operator.');
    }finally{
      setCsrf('');setProfile(null);setHistory([]);setPassword('');setLoading(false);
      setStatus('Signed out of this browser.');
    }
  }

  async function submitTransfer(e:React.FormEvent){
    e.preventDefault();setLoading(true);setError('');
    const cents=Math.round(Number(amount)*100);
    if(!Number.isSafeInteger(cents)||cents<=0||cents>10_000_000||Math.abs(cents/100-Number(amount))>1e-6){
      setError('Enter a valid amount between $0.01 and $100,000.00.');setLoading(false);return;
    }
    try{
      const result=await browserCall<TransferResult>(
        '/transfers','POST',{recipient_email:recipient,amount_cents:cents},csrf,crypto.randomUUID()
      );
      setAmount('');setRecipient('');
      setStatus(result.replayed?'Transfer request already processed.':'Fictional transfer recorded.');
      await refresh();
    }catch(e){setError((e as Error).message);}finally{setLoading(false);}
  }

  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><span className="brandmark"><Activity size={23}/></span><span>Ledger<span className="brandaccent">Flow</span><small>SECURE DEMO</small></span></div>
      <div className="navlabel">SESSION</div>
      <div className="nav active"><ShieldCheck size={18}/> Cookie-protected access</div>
      <div className="sidebottom">Fictional balances only. No real money.</div>
    </aside>
    <main>
      <header><div><div className="eyebrow">SIMULATION / SECURITY</div><h1>LedgerFlow browser demo</h1><p className="muted">A same-origin interface using HttpOnly session cookies and CSRF checks.</p></div>
        {profile&&<button className="soft" disabled={loading} onClick={()=>void signOut()}><LogOut size={16}/> Sign out</button>}
      </header>
      <div className="banner"><ShieldCheck size={18}/> <span><strong>Demo system.</strong> No real payments. Access is restricted to invited fictional demo accounts.</span></div>
      {status&&<p className="success">{status}</p>}
      {error&&<p className="error">{error}</p>}
      {!profile?
        <div className="auth-layout"><div className="auth-copy"><LockKeyhole size={34}/><h2>Secure demonstration access</h2><p>This environment uses same-origin requests. The authentication token is never exposed to browser JavaScript.</p><p>Accounts are provisioned only for the controlled local demonstration.</p></div>
          <form className="panel auth" onSubmit={signIn}><h2>Sign in</h2>
            <label>Email<input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label>
            <label>Password<input type="password" autoComplete="current-password" required minLength={10} value={password} onChange={e=>setPassword(e.target.value)}/></label>
            <button className="primary wide" disabled={loading}>Sign in <ArrowRight size={16}/></button>
          </form></div>
        : <>
          <section className="statgrid"><article className="stat mainstat"><div className="statlabel"><Wallet size={17}/> Simulated balance</div><div className="bigmoney">{formatMoney(profile.balance_cents)}</div><div className="statbottom">{profile.email}</div></article>
            <article className="stat"><div className="statlabel"><Database size={17}/> Recent transactions</div><div className="statnumber">{history.length}</div></article>
          </section>
          <section className="sectiongrid"><article className="panel"><h2>Transfer fictional credits</h2>
              <form onSubmit={submitTransfer}>
                <label>Recipient email<input type="email" required value={recipient} onChange={e=>setRecipient(e.target.value)}/></label>
                <label>Amount (USD)<input type="number" min="0.01" max="100000" step="0.01" required value={amount} onChange={e=>setAmount(e.target.value)}/></label>
                <button className="primary wide" disabled={loading}>Send simulated transfer <ArrowUpRight size={17}/></button>
              </form><p className="muted">Funding is disabled in public staging. This client is for a controlled demo using pre-provisioned fictional balances.</p>
            </article>
            <article className="panel"><h2>Recent activity</h2>
              <div className="history">{history.length?history.map(tx=><div className="transaction" key={tx.id}>
                <strong>{tx.direction==='sent'?'Sent':'Received'}</strong>
                <span>{formatMoney(tx.amount_cents)} · {new Date(tx.created_at).toLocaleDateString()}</span>
              </div>):<p className="muted">No demo transactions recorded.</p>}</div>
            </article></section>
        </>}
      <footer>LedgerFlow · Portfolio prototype · Cookie-based demo mode (opt-in)</footer>
    </main>
  </div>;
}
