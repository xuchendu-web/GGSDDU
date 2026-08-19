# -*- coding: utf-8 -*-
"""Versioned local cache.  Incomplete/legacy entries are never reused."""
import hashlib, json, logging, os, pickle, time
from pathlib import Path
logger=logging.getLogger('iqm.cache')
HERE=Path(__file__).resolve().parent; SKILL_ROOT=HERE.parent; CACHE_VERSION=2
def resolve_cache_dir(explicit=None):
    roots=[Path(explicit)] if explicit else []
    local=os.environ.get('LOCALAPPDATA')
    if local: roots.append(Path(local)/'cjpy-skills'/'cache')
    roots += [Path.home()/'.cache'/'cjpy-skills', SKILL_ROOT/'.cache']
    for d in roots:
        try:
            d.mkdir(parents=True,exist_ok=True); (d/'.iqm-write-probe').touch(exist_ok=True)
            return d
        except OSError as e: logger.debug('cache path unavailable %s: %s',d,e)
    return None
class Cache:
 def __init__(self,cache_dir=None,enabled=True):
  self.dir=resolve_cache_dir(cache_dir); self.enabled=bool(enabled and self.dir); self.last_meta={}; self.stats={'fin_hit':0,'fin_miss':0,'pettm_hit':0,'pettm_miss':0}
 def _path(self,ns,parts): return self.dir/(ns+'_'+hashlib.sha256(repr(parts).encode()).hexdigest()[:24]+'.pkl')
 def _load(self,path,ns):
  try:
   meta=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
   if meta.get('version')!=CACHE_VERSION or not meta.get('complete'): return None
   obj=pickle.loads(path.read_bytes()); self.last_meta[ns]=meta; return obj
  except Exception: return None
 def _save(self,path,obj,meta):
  try:
   meta=dict(meta or {}); meta.update({'version':CACHE_VERSION,'complete':True,'created_at':int(time.time())})
   tmp=path.with_suffix('.tmp'); tmp.write_bytes(pickle.dumps(obj,pickle.HIGHEST_PROTOCOL)); tmp.replace(path)
   path.with_suffix('.json').write_text(json.dumps(meta,ensure_ascii=False,sort_keys=True),encoding='utf-8'); return True
  except Exception as e: logger.warning('cache write failed %s: %s',path,e); return False
 def _get(self,ns,parts):
  if not self.enabled: self.stats[ns+'_miss']+=1; return None
  x=self._load(self._path(ns,parts),ns)
  self.stats[ns+('_hit' if x is not None else '_miss')]+=1; return x
 def _put(self,ns,parts,obj,meta=None):
  if self.enabled: self._save(self._path(ns,parts),obj,meta)
 def get_financial(self,codes,start): return self._get('fin',[tuple(sorted(codes)),start])
 def put_financial(self,codes,start,df,meta=None): self._put('fin',[tuple(sorted(codes)),start],df,meta)
 def get_pettm(self,codes,granularity,window_years,pe_dates,industry_col=None): return self._get('pettm',[tuple(sorted(codes)),granularity,window_years,tuple(pe_dates),industry_col])
 def put_pettm(self,codes,granularity,window_years,pe_dates,df,industry_col=None,meta=None): self._put('pettm',[tuple(sorted(codes)),granularity,window_years,tuple(pe_dates),industry_col],df,meta)
 def summary(self): return dict(self.stats, enabled=self.enabled, directory=str(self.dir) if self.dir else None)
