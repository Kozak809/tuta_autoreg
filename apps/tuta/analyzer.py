"""
Account statistics analyzer for Tuta.

This script analyzes the success and failure rates of Tuta accounts based on
their hardware fingerprints, operating systems, and proxy countries. It reads
the account database and configuration files to provide survival statistics.
"""
import json
import os
import re
from collections import defaultdict
from apps.tuta.tuta_utils import resolve_config_path

# Resolve paths using script directory
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir.endswith('tuta'):
    root_dir = os.path.dirname(os.path.dirname(base_dir))
else:
    root_dir = base_dir

def analyze_accounts(accounts_file):
    valid_configs = []
    invalid_configs = []
    
    # Сначала пытаемся найти файл по указанному пути, если нет - строим абсолютный
    if not os.path.exists(accounts_file):
        accounts_file = os.path.join(root_dir, accounts_file)
        
    with open(accounts_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                acc = json.loads(line)
                status = acc.get('isvalid', '').upper()
                cpath = acc.get('config_path', '')
                
                # Resolve config path
                cfg, real_cpath = resolve_config_path(cpath)
                
                if cfg:
                    if status == 'VALID':
                        valid_configs.append(cfg)
                    elif status == 'INVALID':
                        invalid_configs.append(cfg)
            except Exception as e:
                pass

    return valid_configs, invalid_configs

def extract_proxy_country(proxy_str):
    if not proxy_str: return "Unknown"

    if '#' in proxy_str:
        tag = proxy_str.split('#', 1)[1]
        match = re.search(r'-([A-Z]{2})-', tag)
        if match: return match.group(1)
        # try to extract ISO code from locale if we couldn't get it from proxy string easily
    return "Unknown"

def aggregate_stats(configs):
    stats = {
        'locale': defaultdict(int),
        'timezone': defaultdict(int),
        'platform': defaultdict(int),
        'gpu_vendor': defaultdict(int),
        'proxy_country': defaultdict(int)
    }
    
    for c in configs:
        ctx = c.get('context_args', {})
        hw = c.get('hardware_info', {})
        
        # Locale
        loc = ctx.get('locale', 'Unknown')
        stats['locale'][loc] += 1
        
        # Timezone
        tz = ctx.get('timezone_id', 'Unknown')
        stats['timezone'][tz] += 1
        
        # Platform
        plat = hw.get('platform', 'Unknown')
        if 'Win' in plat: plat = 'Windows'
        elif 'Mac' in plat: plat = 'Mac'
        elif 'Linux' in plat: plat = 'Linux'
        stats['platform'][plat] += 1
        
        # GPU
        gpu = hw.get('gpu', ['Unknown', 'Unknown'])
        vendor = gpu[0] if gpu else 'Unknown'
        stats['gpu_vendor'][vendor] += 1
        
        # Proxy
        proxy = c.get('proxy', '')
        country = extract_proxy_country(proxy)
        if country == "Unknown":
            # fallback to locale for country guess
            country_from_loc = loc.split('-')[-1].upper() if '-' in loc else loc
            stats['proxy_country'][f"FromLocale_{country_from_loc}"] += 1
        else:
            stats['proxy_country'][country] += 1
            
    # Convert default dicts to dicts and sort by values desc
    for k in stats:
        stats[k] = dict(sorted(stats[k].items(), key=lambda item: item[1], reverse=True))
    
    return stats

v, i = analyze_accounts(os.path.join(os.path.dirname(__file__), 'data/accounts.json'))

v_stats = aggregate_stats(v)
i_stats = aggregate_stats(i)

print(f"--- АНАЛИЗ КОНФИГУРАЦИЙ ---")
print(f"Всего ВЫЖИВШИХ (VALID) аккаунтов: {len(v)}")
print(f"Всего ЗАБАНЕННЫХ (INVALID) аккаунтов: {len(i)}")

def print_diff(category, title):
    print(f"\n[{title}]")
    print(f"  {'Значение':<25} | {'VALID':<10} | {'INVALID':<10} | {'% ВЫЖИВАЕМОСТИ'}")
    print("-" * 65)
    
    all_keys = set(v_stats[category].keys()).union(set(i_stats[category].keys()))
    rows = []
    for k in all_keys:
        valid_c = v_stats[category].get(k, 0)
        invalid_c = i_stats[category].get(k, 0)
        total = valid_c + invalid_c
        survival = (valid_c / total * 100) if total > 0 else 0
        rows.append((k, valid_c, invalid_c, survival, total))
        
    rows.sort(key=lambda x: x[4], reverse=True) # sort by total count
    for r in rows:
        print(f"  {r[0]:<25} | {r[1]:<10} | {r[2]:<10} | {r[3]:.1f}%")

print_diff('proxy_country', 'Страна Прокси (предположительно)')
print_diff('platform', 'Платформа (ОС)')
print_diff('gpu_vendor', 'Вендор Видеокарты (GPU)')

