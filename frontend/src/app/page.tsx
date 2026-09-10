'use client';
import { useEffect, useState } from 'react';

type Row = { evidence_id: string; document_id: string; table_id: string; row_id: number; proband_id: string; variant_text: string; phase: string; phase_method: string; match_validation: string; retrieval_links: { direction: string; anchor_row_id: number }[]; raw_cells: Record<string,string> };
type Bundle = { variant: { key:string; gene:string; hgvs_c:string; consequences:string[]; genome_build:string }; input_mode:string; sql_table_evidence:Row[]; rag_text_evidence:{ evidence_id:string; exact_quote:string; document_id:string; retrieval_method:string }[]; catt_grounding:{ status:string; reason?:string; data:Record<string,unknown> }; evidence_assessment:{missing_evidence:string[]}; provenance:Record<string,unknown> };
type Candidate = { variant_key:string; rank:number|null; preference_score:number|null; bundle:Bundle };
type Result = { method:string; ranked_variants:Candidate[]; diagnostics:{ pair_count:number; disagreement_count:number; global_order_available:boolean; coverage:number; judge_calls:number }; pairwise_comparisons:{ variant_1:string; variant_2:string; status:string; forward:{rationale:string}; reverse:{rationale:string} }[] };
type Job = { id:string; status:string; created:string; mode:string; error?:string; result?:Result };
const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

async function request(path:string, options?:RequestInit) {
  const response = await fetch(API + path, options);
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.json();
}

export default function Home() {
  const [jobs,setJobs] = useState<Job[]>([]), [active,setActive] = useState<Job|null>(null);
  const [selected,setSelected] = useState(0), [tab,setTab] = useState('Cases');
  const [corpus,setCorpus] = useState<File|null>(null);
  const [file,setFile] = useState<File|null>(null), [build,setBuild] = useState('GRCh38'), [sample,setSample] = useState('');
  const [busy,setBusy] = useState(false), [error,setError] = useState(''), [connected,setConnected] = useState(false);
  const load = async () => { try { setJobs(await request('/api/runs')); setConnected(true); } catch { setConnected(false); } };
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!active || !['queued','running'].includes(active.status)) return;
    const timer=setInterval(async () => { try { const next=await request('/api/results/'+active.id); setActive(next); if (!['queued','running'].includes(next.status)) void load(); } catch(e) {setError(String(e));} },1000);
    return () => clearInterval(timer);
  },[active]);
  const start=async(demo:boolean) => {
    setBusy(true); setError('');
    try {
      let options:RequestInit={method:'POST'};
      if (!demo) { if (!file) throw new Error('Choose an annotated VCF first.'); const data=new FormData(); data.append('file',file); data.append('genome_build',build); data.append('sample',sample); if(corpus)data.append('literature',corpus); options={...options,body:data}; }
      const job=await request(demo?'/api/demo':'/api/run',options);
      setActive(await request('/api/results/'+job.run_id)); setSelected(0); void load();
    } catch(e) {setError(e instanceof Error?e.message:String(e));} finally {setBusy(false);}
  };
  const choose=async(id:string) => { try {setActive(await request('/api/results/'+id));setSelected(0);} catch(e){setError(String(e));} };
  const result=active?.result, candidate=result?.ranked_variants[selected], bundle=candidate?.bundle;
  const download=() => { if (!result)return; const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`variantrag-${active?.id}.json`;link.click();URL.revokeObjectURL(url); };
  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="VariantRAG home"><span className="brand-icon">⋈</span> Variant<span>RAG</span></a>
      <div className="workspace-label">RESEARCH WORKSPACE</div>
      <div className="nav-active"><span>▧</span> Evidence workbench <span className="nav-dot"/></div>
      <div className="sidebar-section"><span>RECENT RUNS</span><button className="icon-button" onClick={load} aria-label="Refresh runs">↻</button></div>
      <div className="run-list">{jobs.length===0?<p className="muted small">Your analyses will appear here.</p>:jobs.map(job=><button key={job.id} className={'run '+(active?.id===job.id?'selected':'')} onClick={()=>choose(job.id)}><span className={'status-dot '+job.status}/><div><strong>{job.mode==='demo'?'Demonstration':'VCF analysis'}</strong><small>{new Date(job.created).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}</small></div><span className="run-state">{job.status}</span></button>)}</div>
      <div className="sidebar-bottom"><span className={'status-dot '+(connected?'completed':'failed')}/>{connected?'Local API connected':'Local API offline'}<small>v0.2 · DuckDB table engine</small></div>
    </aside>
    <main>
      <header><div className="breadcrumb">Workspace <span>/</span> Evidence workbench</div><span className="local-badge">LOCAL WORKSPACE</span></header>
      <section className="heading"><div><div className="eyebrow">FROM VARIANT TO SOURCE</div><h1>Evidence you can inspect.</h1><p>Trace each candidate through source passages, proband rows, and reproducible comparisons.</p></div><button className="secondary" disabled={!result} onClick={download}>↓ Export results</button></section>
      {!connected&&<div className="notice">Start the local API to run analyses. See the repository walkthrough for the startup command.</div>}
      {error&&<div className="error" role="alert">{error}</div>}
      <section className="input-panel"><div className="input-intro"><span className="step">01</span><h2>Start an analysis</h2><p>Annotated VCF · GRCh37 or GRCh38</p></div><div className="upload-controls"><label className="upload"><span>↑</span><strong>{file?file.name:'Choose an annotated VCF'}</strong><small>.vcf or .vcf.gz · up to 20 MiB</small><input aria-label="Annotated VCF" type="file" accept=".vcf,.vcf.gz" onChange={e=>setFile(e.target.files?.[0]||null)}/></label><label className="corpus-input">Optional evidence corpus <input aria-label="Literature corpus JSON" type="file" accept=".json" onChange={e=>setCorpus(e.target.files?.[0]||null)}/></label><div className="control-row"><label>Genome build<select value={build} onChange={e=>setBuild(e.target.value)}><option>GRCh38</option><option>GRCh37</option></select></label><label>Sample ID <span className="muted">(if multisample)</span><input placeholder="Auto for single sample" value={sample} onChange={e=>setSample(e.target.value)}/></label><button className="primary" disabled={busy||!file||!connected} onClick={()=>start(false)}>Run analysis ↗</button></div></div><div className="demo-panel"><span className="pill">SYNTHETIC DEMO</span><h3>Explore the evidence trail</h3><p>Three candidates. A case table with partner variants above and below the matched row.</p><button className="text-button" disabled={busy||!connected} onClick={()=>start(true)}>Open demonstration →</button></div></section>
      {active&&<div className="run-heading"><h2>{active.mode==='demo'?'Demonstration analysis':'VCF analysis'}</h2><span className={'pill '+(active.status==='failed'?'danger':'')}>{active.status}</span><code>{active.id.slice(0,8)}</code></div>}
      {active?.status==='failed'&&<div className="error" role="alert">{active.error}</div>}
      {active&&['queued','running'].includes(active.status)&&<div className="empty"><div className="loading"/><h3>Assembling evidence</h3><p>Parsing alleles, retrieving case rows, and recording comparisons.</p></div>}
      {result&&<>
        {active?.mode==='demo'&&<div className="demo-note">Synthetic demonstration — all variants, genes, and case facts below are invented test fixtures.</div>}
        <div className="metrics"><div><span>CANDIDATES</span><strong>{result.ranked_variants.length.toString().padStart(2,'0')}</strong><small>Allele-specific filtering</small></div><div><span>PAIRS COMPARED</span><strong>{result.diagnostics.pair_count.toString().padStart(2,'0')}</strong><small>Both presentation orders</small></div><div><span>ORDER DISAGREEMENTS</span><strong>{result.diagnostics.disagreement_count.toString().padStart(2,'0')}</strong><small>Retained for inspection</small></div><div><span>RANKING METHOD</span><strong className="metric-text">Evidence availability</strong><small>Deterministic research baseline</small></div></div>
        {!result.diagnostics.global_order_available&&<div className="notice">No defensible global ordering is available from these comparisons. Candidates remain unranked.</div>}
        <div className="results-grid"><section className="candidate-panel"><div className="panel-title"><h2>Candidates</h2><span>{result.ranked_variants.length} retained</span></div>{result.ranked_variants.map((item,index)=><button className={'candidate '+(index===selected?'active':'')} key={item.variant_key} onClick={()=>setSelected(index)}><span className="rank">{item.rank??'—'}</span><div><strong>{item.bundle.variant.gene||'Unmapped gene'}</strong><code>{item.bundle.variant.hgvs_c||item.variant_key}</code><small>{item.bundle.variant.consequences.join(', ').replaceAll('_',' ')}</small></div><span className="candidate-count">{item.bundle.sql_table_evidence.length}<small>rows</small></span></button>)}<div className="panel-footnote">Preference scores measure review priority. They are not clinical probabilities.</div></section>
        <section className="evidence-panel">{bundle?<><div className="evidence-title"><div><span className="eyebrow">EVIDENCE DOSSIER</span><h2>{bundle.variant.gene||'Candidate'} <span>{bundle.variant.hgvs_c||bundle.variant.key}</span></h2></div><span className="pill">{bundle.variant.genome_build}</span></div><div className="tabs" role="tablist">{['Cases','Text','Grounding','Comparisons','Provenance'].map(name=><button role="tab" aria-selected={tab===name} className={tab===name?'active':''} onClick={()=>setTab(name)} key={name}>{name}</button>)}</div><div className="tab-content">
        {tab==='Cases'&&<><div className="section-description"><h3>Proband context, in source order</h3><p>A matched row expands to earlier and later rows with the same proband ID in this table.</p></div>{bundle.sql_table_evidence.length?<div className="table-scroll"><table><thead><tr><th>Source row</th><th>Proband</th><th>Variant / source cells</th><th>Phase</th></tr></thead><tbody>{bundle.sql_table_evidence.map(row=><tr key={row.evidence_id} className={row.match_validation==='exact_allele'?'matched':''}><td><span className="row-direction">{row.retrieval_links.map(l=>l.direction).join(', ')}</span><small>{row.document_id} · {row.table_id} · {row.row_id}</small></td><td><strong>{row.proband_id||'Unspecified'}</strong></td><td><details><summary>{row.raw_cells.variant||row.variant_text}</summary><pre>{JSON.stringify(row.raw_cells,null,2)}</pre></details></td><td><span className="pill">{row.phase}</span><small>{row.phase_method||'Not established'}</small></td></tr>)}</tbody></table></div>:<div className="empty compact">No exact-allele case evidence was recovered.</div>}<div className="method-note">Same-proband retrieval identifies context. Co-occurrence alone does not establish that variants are in trans.</div></>}
        {tab==='Text'&&(bundle.rag_text_evidence.length?bundle.rag_text_evidence.map(hit=><article className="quote" key={hit.evidence_id}><span className="eyebrow">{hit.document_id}</span><blockquote>{hit.exact_quote}</blockquote><small>{hit.retrieval_method}</small></article>):<div className="empty compact">No text evidence was recovered.</div>)}
        {tab==='Grounding'&&<div><h3>CATT precision grounding</h3><p>Status: <span className="pill">{bundle.catt_grounding.status.replaceAll('_',' ')}</span></p><p className="muted">{bundle.catt_grounding.reason||'No verified CATT source snapshot was supplied for this run.'}</p>{bundle.catt_grounding.status==='available'&&<pre>{JSON.stringify(bundle.catt_grounding.data,null,2)}</pre>}</div>}
        {tab==='Comparisons'&&result.pairwise_comparisons.filter(p=>[p.variant_1,p.variant_2].includes(bundle.variant.key)).map((pair,i)=><article className="comparison" key={i}><span className="pill">{pair.status}</span><code>{pair.variant_1} ↔ {pair.variant_2}</code><h4>Forward presentation</h4><p>{pair.forward.rationale}</p><h4>Swapped presentation</h4><p>{pair.reverse.rationale}</p></article>)}
        {tab==='Provenance'&&<><h3>Missing evidence & limitations</h3><ul className="limitations">{bundle.evidence_assessment.missing_evidence.map(item=><li key={item}>{item}</li>)}</ul><details><summary>Inspect provenance manifest</summary><pre>{JSON.stringify(bundle.provenance,null,2)}</pre></details></>}
        </div></>:<div className="empty compact">No candidates passed the configured filters.</div>}</section></div>
      </>}
      {!active&&<section className="welcome"><div className="welcome-mark">⌁</div><h2>Every claim starts with a source.</h2><p>Run the demonstration to inspect matched variants, recovered partner rows,<br/>and the rationale behind each comparison.</p><div className="welcome-labels"><span>01 / Allele identity</span><span>02 / Source evidence</span><span>03 / Auditable comparison</span></div></section>}
      <footer>VariantRAG <span>Research evidence workbench · Reproducible by design</span><span>Sources before scores.</span></footer>
    </main>
  </div>;
}
