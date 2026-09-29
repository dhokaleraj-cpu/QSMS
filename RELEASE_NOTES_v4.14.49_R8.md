# QCMS 4.14.49 R8

OSP Material Out now accepts multiple released RMTC/source lots and different heat numbers for one part under one vendor/process/challan document. Each line has its own dispatched and sample quantity, FSI batch, receipt balance and quality status.

Sample receipt, partial inward, Dimensional and MetLab tracking remain separate by heat batch. A consolidated Material Out PDF lists every heat. Grouped edit/delete use existing downstream safeguards and execute atomically. Failed saves leave no partially created dispatch; repeat saves reuse the original document request.

The additive database migration is already applied and verified on the existing QSMS production project. No business data was modified. Download the R8 updater and run it to install/push the cumulative application source. GitHub then builds the Android APK using the existing workflow.
