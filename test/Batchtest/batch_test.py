#!/usr/bin/python
# -*- coding: utf-8 -*-

import os

def run (*commands):
  cmd = " ".join(commands);
  print "========== $",cmd;
  code = os.system(cmd);
  if code:
    raise RuntimeError,"failed with exit code %x"%code;

def verify_image (file1,file2,maxdelta=1e-6):
  import pyfits
  im1 = pyfits.open(file1)[0].data;
  im2 = pyfits.open(file2)[0].data;
  # trim corners, as these may have differences due to modifications of the tapering scheme
  im1 = im1[...,20:-20,20:-20];
  im2 = im2[...,20:-20,20:-20];
  delta = abs(im1-im2).max();
  if delta > maxdelta:
    raise RuntimeError,"%s and %s differ by %g"%(file1,file2,delta);
  print "%s and %s differ by %g, this is within tolerance"%(file1,file2,delta);

if __name__ == '__main__':

  ## make simulated MS
  print "========== Removing files";
  run("rm -fr WSRT.MS* WSRT*img WSRT*fits");
  print "========== Running makems";
  run("makems WSRT_makems.cfg");
  run("mv WSRT.MS_p0 WSRT.MS");
  run("ls WSRT.MS");
  run("lwimager ms=WSRT.MS data=CORRECTED_DATA mode=channel weight=natural npix=10");

  from Timba.Apps import meqserver
  from Timba.TDL import Compile
  from Timba.TDL import TDLOptions

  # This starts a meqserver. Note how we pass the "-mt 2" option to run two threads.
  # A proper pipeline script may want to get the value of "-mt" from its own arguments (sys.argv).
  print "Starting meqserver";
  mqs = meqserver.default_mqs(wait_init=10,extra=["-mt","2"]);

  try:
    ## make simulation with perfect MODEL_DATA
    script = "testing-sim.py";
    print "========== Compiling",script;
    TDLOptions.config.read("testing.tdl.conf");
    mod,ns,msg = Compile.compile_file(mqs,script,config="simulate-model");
    print "========== Simulating MODEL_DATA ";
    mod._tdl_job_1_simulate_MS(mqs,None,wait=True);
    print "========== Imaging MODEL_DATA ";
    TDLOptions.get_job_func('Make a dirty image')(mqs,None,wait=True,run_viewer=False);

    ## compare against reference image
    print "========== Verifying test image ";
    verify_image('WSRT.MS.MODEL_DATA.channel.1ch.fits','test-refimage.fits',maxdelta=1e-3);

    print "========== Compiling script with modified config";
    TDLOptions.init_options("simulate-model",save=False);
    TDLOptions.set_option("me.enable_G",True);
    mod,ns,msg = Compile.compile_file(mqs,script,config=None);
    print "========== Simulating DATA ";
    TDLOptions.set_option("ms_sel.output_column","DATA");
    mod._tdl_job_1_simulate_MS(mqs,None,wait=True);
    print "========== Imaging DATA ";
    TDLOptions.set_option("img_sel.imaging_column","DATA");
    TDLOptions.get_job_func('Make a dirty image')(mqs,None,wait=True,run_viewer=False);

    ## calibrate
    script = "testing-cal.py";
    print "========== Compiling",script;
    mod,ns,msg = Compile.compile_file(mqs,script,config="calibrate");
    print "========== Calibrating ";
    TDLOptions.get_job_func('Calibrate G diagonal terms')(mqs,None,wait=True);
    print "========== Imaging MODEL_DATA ";
    TDLOptions.get_job_func('Make a dirty image')(mqs,None,wait=True,run_viewer=False);

    ## compare against reference image
    print "========== Verifying residual image ";
    verify_image('WSRT.MS.CORRECTED_DATA.channel.1ch.fits','test-refresidual.fits',maxdelta=1e-3);

    ## all tests succeeded
    print "========== Break out the bubbly, this hog is airborne!";

  finally:
    print "Stopping meqserver";
    # this halts the meqserver
    meqserver.stop_default_mqs();
    # now we can exit
    print "Bye!";

