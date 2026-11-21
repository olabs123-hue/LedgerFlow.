import {useState} from 'react';
import {Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, CreditCard, Database, ShieldCheck, Wallet} from 'lucide-react';
type Record = {id:number; direction:'sent'|'received';amount:number;label:string};
const initial:Record[]=[
  {id:1045,direction:'sent',amount:12500,label:'Vendor settlement'},
  {id:1044,direction:'received',amount:40000,label:'Demo deposit'},
  {id:1043,direction:'sent',amount:5900,label:'Services payment'},
];
const money=(c:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(c/100);
export default function Showcase(){
  const [history,setHistory]=useState<Record[]>(initial);
  const [balance,setBalance]=useState(215640);
  const [recipient,setRecipient]=useState('alex@example.com');
  const [amount,setAmount]=useState('25');
  const [notice,setNotice]=useState('');
  function simulate(e:React.FormEvent){
    e.preventDefault();
    const cents=Math.round(Number(amount)*100);
    if(!Number.isSafeInteger(cents)||cents<=0||cents>balance){setNotice('Enter a valid amount within your fictional balance.');return;}
    setBalance(b=>b-cents);
    setHistory(h=>[{id:1046+h.length-3,direction:'sent',amount:cents,label:recipient},...h]);
    setNotice('Simulated transfer recorded locally in your browser. No API request was made.');
  }
  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><span className="brandmark"><Activity size={23}/></span><span>Ledger<span className="brandaccent">Flow</span><small>FINANCIAL OPERATIONS</small></span></div>
      <div className="navlabel">WORKSPACE</div><div className="nav active"><Wallet size={18}/> Overview</div>
      <div className="nav"><CreditCard size={18}/> Transactions</div>
      <div className="navlabel">PLATFORM</div><div className="nav"><Database size={18}/> Ledger showcase</div>
      <div className="sidebottom"><span className="livecircle"/> Offline showcase <small>Illustrative data only.</small></div>
    </aside>
    <main>
      <header><div><div className="eyebrow">OPERATIONS / DEMONSTRATION</div><h1>Financial overview</h1><p className="muted">Explore a portfolio preview of LedgerFlow's financial operations UI.</p></div><span className="env">INTERACTIVE PREVIEW</span></header>
      <div className="banner"><ShieldCheck size={18}/><span><strong>Safe portfolio demonstration:</strong> All balances and transactions are fictional. This preview runs entirely in your browser—no accounts, database or payment APIs.</span></div>
      <section className="statgrid">
        <article className="stat mainstat"><div className="statlabel"><Wallet size={17}/> Fictional balance</div><div className="bigmoney">{money(balance)}</div><div className="statbottom">Preview account <span>USD · FICTIONAL</span></div></article>
        <article className="stat"><div className="statlabel"><ArrowUpRight size={17}/> Transfers shown</div><div className="statnumber">{history.filter(x=>x.direction==='sent').length}</div><div className="statbottom">Illustrative entries</div></article>
        <article className="stat"><div className="statlabel"><ArrowDownLeft size={17}/> Deposits shown</div><div className="statnumber">{history.filter(x=>x.direction==='received').length}</div><div className="statbottom">Illustrative entries</div></article>
      </section>
      <section className="sectiongrid">
        <article className="panel"><div className="panelhead"><div><div className="eyebrow">DEMO WORKFLOW</div><h2>Simulate transfer</h2><p className="muted">Try the interaction. No money or network request is involved.</p></div><div className="roundicon"><ArrowUpRight size={22}/></div></div>
          <form onSubmit={simulate}><label>Recipient label<input required value={recipient} onChange={e=>setRecipient(e.target.value)} maxLength={100}/></label><label>Fictional amount (USD)<input type="number" min="0.01" max="10000" step="0.01" required value={amount} onChange={e=>setAmount(e.target.value)}/></label><button className="primary wide">Simulate transfer <ArrowRight size={17}/></button></form>
          {notice&&<p className="success">{notice}</p>}<p className="muted">Refresh the page to reset this preview.</p>
        </article>
        <article className="panel"><div className="panelhead"><div><div className="eyebrow">PREVIEW AUDIT TRAIL</div><h2>Recent activity</h2><p className="muted">Sample transactions for interface exploration.</p></div></div>
          <div className="history">{history.map(x=><div className="transaction" key={x.id}><div className={'txicon '+(x.direction==='received'?'incoming':'')}>{x.direction==='sent'?<ArrowUpRight size={18}/>:<ArrowDownLeft size={18}/>}</div><div><strong>{x.label}</strong><small>DEMO-{x.id}</small></div><b className={x.direction==='received'?'positive':''}>{x.direction==='received'?'+':'−'}{money(x.amount)}</b></div>)}</div>
        </article>
      </section>
      <footer><span>LedgerFlow · Browser-only showcase · No financial services offered</span><a href="https://github.com/olabs123-hue/LedgerFlow.">View tested full-stack source on GitHub</a></footer>
    </main>
  </div>;
}
