"""Reproducible synthetic English case training; never uses uploaded user documents."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import os
from pathlib import Path
import random
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from ocr import prepare_cell
import native_ocr


def generate(root, augmented=False):
    words=Path(__file__).with_name('english_words_500.txt').read_text().splitlines()
    unseen=Path(__file__).with_name('english_unseen_100.txt').read_text().splitlines()
    assert len(words)==len(set(words))==500 and not set(words)&set(unseen)
    fonts={'train':['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf','/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf','/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf'],
           'validation':['/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf','/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf'],
           'unseen':['/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf','/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf']}
    if not augmented:
        fonts['train']=fonts['train'][:2]
    rows=[]
    for split,font_paths in fonts.items():
        folder=root/split;folder.mkdir(parents=True,exist_ok=True)
        for i,word in enumerate(unseen if split=='unseen' else words):
            for case,text in [('lower',word),('upper',word.upper()),('title',word.title())]:
                for face,font_path in enumerate(font_paths):
                    size=(16 if augmented and (i+face)%2 else 24) if split=='train' else 19
                    font=ImageFont.truetype(font_path,size)
                    box=font.getbbox(text)
                    image=Image.new('L',(box[2]-box[0]+24,56),255)
                    ImageDraw.Draw(image).text((12-box[0],8-box[1]),text,font=font,fill=0)
                    pixels=prepare_cell(np.array(image))
                    base=folder/f'w{i:03}-{case}-f{face}'
                    Image.fromarray(pixels).save(base.with_suffix('.tif'))
                    base.with_suffix('.gt.txt').write_text(text+'\n',encoding='utf-8')
                    h,w=pixels.shape
                    base.with_suffix('.box').write_text(''.join(f'{ch} 0 0 {w} {h} 0\n' for ch in text)+f'\t 0 0 {w} {h} 0\n',encoding='utf-8')
                    rows.append(dict(split=split,word=word,case=case,text=text,font=Path(font_path).name,image=str(base.with_suffix('.tif'))))
    (root/'manifest.json').write_text(json.dumps(rows,indent=2))
    return rows


def evaluate(rows,lang):
    def recognize(row):
        image=np.array(Image.open(row['image']))
        text=native_ocr.read(image,lang,7)
        return {**row,'actual':text,'exact':text==row['text'],'casefold_correct':text.casefold()==row['text'].casefold()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        predictions=list(pool.map(recognize,rows))
    report={}
    for split in ['validation','unseen']:
        subset=[r for r in predictions if r['split']==split]
        report[split]={'total':len(subset),'exact':sum(r['exact'] for r in subset),'casefold_correct':sum(r['casefold_correct'] for r in subset)}
    return predictions,report


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--iterations',type=int);ap.add_argument('--profile',choices=['initial','augmented'],default='initial')
    args=ap.parse_args();root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    rows=generate(root,args.profile=='augmented')
    if args.iterations is None:
        args.iterations=8000 if args.profile=='augmented' else 4000
    print('Generated 500 words in lower/upper/title case;',sum(r['split']=='train' for r in rows),'training; 3000 separate-font validation; 600 unseen-word tests',flush=True)
    check=[r for r in rows if r['split']!='train']
    predictions,report=evaluate(check,'eng_best')
    (root/'baseline-predictions.json').write_text(json.dumps(predictions,indent=2));(root/'baseline-report.json').write_text(json.dumps(report,indent=2))
    print('Baseline:',json.dumps(report),flush=True)
    train=[r for r in rows if r['split']=='train'];random.Random(500).shuffle(train)
    assert args.iterations>=len(train), 'At least one full training pass is required'
    def lstmf(row):
        image=Path(row['image']);base=image.with_suffix('')
        p=subprocess.run(['tesseract',str(image),str(base),'-l','eng_best','--psm','7','/usr/share/tesseract-ocr/5/tessdata/configs/lstm.train'],capture_output=True,text=True)
        if p.returncode or not base.with_suffix('.lstmf').exists():raise RuntimeError(p.stderr)
        return str(base.with_suffix('.lstmf'))
    with ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(lstmf,train))
    (root/'train.list').write_text('\n'.join(files)+'\n')
    model=root/'model';model.mkdir(exist_ok=True)
    source=Path(os.environ['TESSDATA_PREFIX'])/'eng_best.traineddata'
    assert hashlib.file_digest(source.open('rb'),'sha256').hexdigest()=='8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba', 'Unexpected source model'
    subprocess.run(['combine_tessdata','-e',str(source),str(model/'eng.lstm')],check=True,capture_output=True)
    print('Training',args.iterations,'iterations; validation/unseen images are not passed to trainer',flush=True)
    cmd=['lstmtraining','--continue_from',str(model/'eng.lstm'),'--traineddata',str(source),'--train_listfile',str(root/'train.list'),'--model_output',str(model/'english-case'),'--max_iterations',str(args.iterations),'--learning_rate','0.00002' if args.profile=='augmented' else '0.0001','--target_error_rate','-1','--sequential_training','true','--debug_interval','0']
    with (root/'training.log').open('w') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0
    checkpoint=model/'english-case_checkpoint'
    subprocess.run(['lstmtraining','--stop_training','--continue_from',str(checkpoint),'--traineddata',str(source),'--model_output',str(model/'eng_case.traineddata')],check=True,capture_output=True)
    evaluation_dir=root/'evaluation-tessdata';evaluation_dir.mkdir(exist_ok=True)
    for name,target in [('eng_best',source.resolve()),('eng_case',(model/'eng_case.traineddata').resolve())]:
        alias=evaluation_dir/(name+'.traineddata')
        if alias.exists() or alias.is_symlink():alias.unlink()
        alias.symlink_to(target)
    original_prefix=os.environ['TESSDATA_PREFIX']
    try:
        os.environ['TESSDATA_PREFIX']=str(evaluation_dir)
        predictions,report=evaluate(check,'eng_case')
    finally:
        os.environ['TESSDATA_PREFIX']=original_prefix
    (root/'trained-predictions.json').write_text(json.dumps(predictions,indent=2));(root/'trained-report.json').write_text(json.dumps(report,indent=2))
    print('Trained:',json.dumps(report),flush=True)

if __name__=='__main__':main()
