#!/usr/bin/python
import sys
sys.path.append('/home/ubuntu/TOOLS/Scripts/alignment')
sys.path.append('/home/ubuntu/TOOLS/Scripts/utility')
import os
import re
from date_time import date_time
from fastx_se import fastx_se
from bwa_mem_se import bwa_mem_se
from novosort_sort_se import novosort_sort_se
from picard_rmdup import picard_rmdup
from flagstats import flagstats
import coverage
from subprocess import call
import subprocess
import json
from log import log
from update_couchdb import update_couchdb
import pdb

class Pipeline():
    def __init__(self,end1,seqtype,json_config,ref_mnt):
        self.json_config = json_config
        self.end1=end1
        self.seqtype=seqtype
        self.status=0
        self.ref_mnt=ref_mnt
        self.parse_config()

    def parse_config(self):
        self.config_data = json.loads(open(self.json_config, 'r').read())
        s=re.match('^(\S+)_1_sequence\.txt\.gz$',self.end1)
        if s:
            self.sample=s.group(1)
        else:
            #s=re.match('(^\S+)_\D*\d\.f\w*q\.gz$',self.end1)
            # T1_ATCACG_L005_R1_001.fastq.gz
            s=re.match('(^\S+)\.f\w*q\.gz$',self.end1)
            try:
                self.sample=s.group(1)
            except:
                sys.stderr.write('Could not fit pattern for ' + self.end1 + '\n')
                exit(1)
        self.loc='LOGS/' + self.sample + '.pipe.log'
        HGACID=self.sample.split("_")
        self.bid=HGACID[0]
        self.fastx_tool=self.config_data['tools']['fastx']
        self.bwa_tool=self.config_data['tools']['bwa']
        self.bwa_ref=self.ref_mnt + '/' + self.config_data['refs']['bwa']
        self.samtools_tool=self.config_data['tools']['samtools']
        self.samtools_ref=self.ref_mnt + '/' + self.config_data['refs']['samtools']
        self.java_tool=self.config_data['tools']['java']
        self.picard_tool=self.config_data['tools']['picard']
        self.novosort=self.config_data['tools']['novosort']
        self.picard_tmp='picard_tmp'
        self.bedtools2_tool=self.config_data['tools']['bedtools']
        self.bed_ref=self.ref_mnt + '/' + self.config_data['refs'][self.seqtype]
        self.obj=self.config_data['refs']['obj']
        self.cont=self.config_data['refs']['cont']
        self.qc_stats=self.config_data['tools']['qc_stats']
        self.threads=self.config_data['params']['threads']
        self.ram=self.config_data['params']['ram']
        self.pipeline()

    def pipeline(self):
        log_dir='LOGS/'
        if os.path.isdir(log_dir) == False:
            mk_log_dir='mkdir ' + log_dir
            call(mk_log_dir,shell=True)
            log(self.loc,date_time() + 'Made log directory ' + log_dir + "\n")
        # create BAM and QC directories if they don't exist already
        bam_dir='BAM/'
        qc_dir='QC/'
        if os.path.isdir(bam_dir) == False:
            mk_bam_dir='mkdir ' + bam_dir
            call(mk_bam_dir,shell=True)
            log(self.loc,date_time() + 'Made bam directory ' + bam_dir + "\n")
        if os.path.isdir(qc_dir) == False:
            mk_qc_dir='mkdir ' + qc_dir
            call(mk_qc_dir,shell=True)
            log(self.loc,date_time() + 'Made qc directory ' + qc_dir + "\n")
        log(self.loc,date_time() + "Starting alignment qc for paired end sample files " + self.end1 + "\n")
        #inputs
        
        SAMPLES={}
        SAMPLES[self.sample]={}
        SAMPLES[self.sample]['f1']=self.end1
        RGRP="@RG\\tID:" + self.sample + "\\tLB:" + self.bid + "\\tSM:" + self.bid + "\\tPL:illumina"
        
        #tools and refs
    
        wait_flag=1
        # check certain key processes
        
        check=bwa_mem_se(self.bwa_tool,RGRP,self.bwa_ref,self.end1,self.samtools_tool,self.samtools_ref,self.sample,log_dir,self.threads) # rest won't run until completed
        if(check != 0):
            log(self.loc,date_time() + 'BWA failure for ' + self.sample + '\n')
            exit(1)
        
        log(self.loc,date_time() + 'Getting fastq quality score stats\n')
        fastx_se(self.fastx_tool,self.sample,self.end1) # will run independently of rest of output
        log(self.loc,date_time() + 'Sorting BAM file\n')

        check=novosort_sort_se(self.novosort,self.sample,log_dir,self.threads,self.ram) # rest won't run until completed
        if(check != 0):
            log(self.loc,date_time() + 'novosort sort failure for ' + self.sample + '\n')
            exit(1)
        log(self.loc,date_time() + 'Removing PCR duplicates\n')
        picard_rmdup(self.java_tool,self.picard_tool,self.picard_tmp,self.sample,log_dir,self.ram)  # rest won't run until emopleted
        log(self.loc,date_time() + 'Gathering SAM flag stats\n')
        flagstats(self.samtools_tool,self.sample) # flag determines whether to run independently or hold up the rest of the pipe until completion
        #figure out which coverage method to call using seqtype
        log(self.loc,date_time() + 'Calculating coverage for ' + self.seqtype + '\n')
        method=getattr(coverage,(self.seqtype+'_coverage'))

        method(self.bedtools2_tool,self.sample,self.bed_ref,wait_flag) # run last since this step slowest of the last
        log(self.loc,date_time() + 'Checking outputs and uploading results\n')
        # check to see if last expected file was generated search for seqtype + .hist suffix
        flist=os.listdir('./')
        suffix=self.seqtype+'.hist'
        for fn in flist:
            if fn==(self.sample +'.' + suffix):
                self.status=1
                break
        if self.status==1:
            p_tmp_rm="rm -rf picard_tmp"
            call(p_tmp_rm,shell=True)
            # move files into approriate place and run qc_stats
            log(self.loc,date_time() + 'Calculating qc stats and prepping files for uplaod\n')
            mv_bam='mv *.bam *.bai BAM/'
            subprocess.call(mv_bam,shell=True)
            qc_cmd=self.qc_stats + ' 2 ' + self.sample
            subprocess.call(qc_cmd,shell=True)
            rm_sf='rm ' + self.end1
            subprocess.call(rm_sf,shell=True)
            mv_rest='find . -maxdepth 1 -type f -exec mv {} QC \;'
            subprocess.call(mv_rest, shell=True)
            from upload_to_swift import upload_to_swift
            obj=self.obj + "/" + self.bid
            check=upload_to_swift(self.cont,obj)
            if check==0:
                create_list='ls QC/*qc_stats.json > QC/' + self.sample + '_qc_stats.list'
                subprocess.call(create_list,shell=True)
                uc=update_couchdb('QC/' + self.sample + '_qc_stats.list')
                if uc==0:
                    log(self.loc,date_time() + 'Couchdb successfully updated\n')
                    self.status = 0                    
                    log(self.loc,date_time() + "Pipeline complete, files successfully uploaded.  Files may be safely removed\n")
                else:
                    self.status = 1
                    log(self.loc,date_time() + "CouchDB update failed! Check database server connection\n")
                
            else:
                log(self.loc,date_time() + "All but file upload succeeded\n")
                self.status = 1
        else:
            (self.loc,date_time() + "File with suffix " + suffix + " is missing!  If intentional, ignore this message.  Otherwise, check logs for potential failures\n")
            self.status = 1

def main():
    import argparse
    parser=argparse.ArgumentParser(description='DNA alignment paired-end QC pipeline')
    parser.add_argument('-f1','--file1',action='store',dest='end1',help='First fastq file')
    parser.add_argument('-t','--seqtype',action='store',dest='seqtype',help='Type of sequencing peformed.  Likely choices are genome, exome, and capture')
    parser.add_argument('-j','--json',action='store',dest='config_file',help='JSON config file containing tool and reference locations')
    parser.add_argument('-m','--mount',action='store',dest='ref_mnt',help='Drive mount location.  Example would be /mnt/cinder/REFS_XXX')
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    inputs=parser.parse_args()

    end1=inputs.end1
    seqtype=inputs.seqtype
    config_file=inputs.config_file
    ref_mnt=inputs.ref_mnt
    Pipeline(end1,seqtype,config_file,ref_mnt)
if __name__ == "__main__":
    main()
