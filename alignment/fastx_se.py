#!/usr/bin/python
import sys
sys.path.append('/home/ubuntu/TOOLS/Scripts/utility')
import os
from date_time import date_time
from subprocess import Popen
from subprocess import call
from log import log

def fastx_se(fastx_tool,sample,end1):
    # casual logging - look for a LOGS directory, otherwise assume current dir
    log_dir='./'
    if os.path.isdir('LOGS'):
        log_dir='LOGS/'
    # assumes phred 64, try phred 33 if it fails
    loc=log_dir + sample + '.fastx.log'
    fastx_cmd='gzip -dc ' + end1 + ' | ' + fastx_tool + ' -N -o ' + sample + '.qs'
    log(loc,date_time() + fastx_cmd + "\n")
    f1=Popen(fastx_cmd,shell=True,stdin=None,stdout=None,stderr=None,close_fds=True)
    # check after a minute whether the process is still good - shouldn't take too long to ascertain whether phred score didn't fit
    call('sleep 20s', shell=True)

    if str(f1.poll()) == '1':
        try:
            log(loc,date_time() + 'Assuming phred 64 failed, trying phred 33\n')
            fastx_cmd='gzip -dc ' + end1 + ' | ' + fastx_tool + ' -Q33 -N -o ' + sample + '.qs'
            log(loc,date_time() + fastx_cmd + "\n")
            f1=Popen(fastx_cmd,shell=True,stdin=None,stdout=None,stderr=None,close_fds=True)
        except:
            log(loc,date_time() + 'Still didn\'t find correct scoring system\n')
            exit(1)
    return 0

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(description='FASTX quality stats module.  Provides quality stats for fastq file and is independent of alignment.')
    parser.add_argument('-f','--fastx',action='store',dest='fastx_tool', help='Location of fastx_quality_stats tool.  Version 0.0.13.2 preferred.')
    parser.add_argument('-sa','--sample',action='store',dest='sample',help='Sample/location name prefix')
    parser.add_argument('-f1','--file1',action='store',dest='end1',help='Fastq file')

    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    inputs=parser.parse_args()
    (fastx_tool,sample,end1)=(inputs.fastx_tool,inputs.sample,inputs.end1)
    fastx_se(fastx_tool,sample,end1)
