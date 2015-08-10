;;
;;
;; Recipe for coloring SenSyF S2 outputs:
;;
;; Preconditions:
;;   - Byte-valued GeoTIFF file created as 'byte_onset.tiff'
;;
;; Steps:
;;  - Load one of the color tables below to the variable CT
;;    IDL> CT_SENSYF_S2, /ONSET, CT=CT  ; Replace /ONSET with /PEAK or /END 
;;
;;  - Create ENVI reader for uncolored product
;;    IDL> onr = ENVI_GEOTIFF_READER('byte_onset.tiff')
;;
;;  - Add color table to ENVI object
;;    IDL> onr->setinfo, updatestruct(onr->getinfo(), 'class_lookup', transpose(CT))
;;
;;  - Create GeoTIFF backend, and make it dump data to 'colored_onset.tiff'
;;    IDL> gtb = envi_geotiff_backend(onr)
;;    IDL> gtb->write, 'colored_onset.tiff'
;;
;;  - Create VRT file from colored and uncolored GeoTIFF files
;;    $ gdal_translate -of VRT byte_onset.tiff onset_nocolor.vrt
;;    $ gdal_translate -of VRT colored_onset.tiff onset_color.vrt
;;
;;  - Isolate the difference as an ed script
;;    $ diff -e onset_nocolor.vrt onset_color.vrt > colorize_onset.ed
;;
;;  - Edit the ed script
;;    Keep only two chunks:
;;     1. the chunk which changes SourceFileName to tmp.tiff
;;        - change the addressing line (e.g. '61c') to
;;        /SourceFilename/c
;;     2. the chuck which changes ColorInterp and adds ColorTable
;;        - change the addressing line (e.g. '63c') to
;;        /ColorInterp/c
;;     After the final period, add two more lines containing
;;     w
;;     q
;;     This is necessary for ed to save the results of the edit.
;;
;;  - from onset_nocolor.vrt, create onset.vrt by applying patch
;;    $ cp onset_nocolor.vrt onset.vrt
;;    $ ed -s onset.vrt < colorize_onset.ed
;;
;;    Three ed scripts have been generated this way:
;;            colorize_{onset,peak,end}.ed
;;    These can be applied to a VRT file generated from an uncolored
;;    GeoTIFF regardless of its projection and geometry.
;;
;;  - Colorize products
;;    Using the modified VRT file to add colors to the GeoTIFF is done using the
;;    python script 'apply_ctab.py'.
;;
;;
;; ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;; Production ;;;;;;;;;;;;;;;;;;;;;;;;;
;;
;;  - Given ed scripts created as explained above, the shell script called
;;    'do_colorize' reads names of GeoTIFF files from STDIN and adds color
;;    tables to them, as long as their names contain 'onset', 'peak' or 'end'.
;;
;;


pro _$ctss$_values, ct, values

    vdim = size(values, /dimensions)
    nrows = vdim[1]

    early = values[0,0]
    for ii = 0, early do ct[ii,*] = values[1:*,0]

    late = values[0,nrows-1]
    for ii = late, 199 do ct[ii,*] = values[1:*,nrows-1]

    for ii = 1, nrows-2 do begin
        ifirst = values[0, ii]
        ilast = values[0, ii+1]-1
        ilen = ilast - ifirst
        ct[ifirst,*] = values[1:*, ii]
        if ilen gt 0 then begin
            dval = float(values[1:*,ii+1] - values[1:*, ii]) / (ilen+1)
            for jj=1,ilen do $
                ct[ifirst+jj, *] = values[1:*, ii] + jj * dval
        endif
    endfor
end


function _$ctss$_onset_values
    compile_opt hidden, idl2, logical_predicate
    return, [ $
        [ 50, 150, 150, 150], $
        [ 51, 145,  46,   0], $
        [ 52, 145,  46,   0], $
        [ 53, 135,  65,   0], $
        [ 54, 122,  80,   0], $
        [ 55, 112,  90,   0], $
        [ 56, 102,  99,   0], $
        [ 57,  77,  89,   0], $
        [ 58,  55,  79,   0], $
        [ 59,  35,  66,   0], $
        [ 60,  22,  56,   0], $
        [ 61,  27,  66,   0], $
        [ 62,  37,  79,   0], $
        [ 63,  47,  94,   0], $
        [ 64,  58, 110,   0], $
        [ 65,  71, 125,   0], $
        [ 66,  86, 143,   0], $
        [ 67,  99, 161,   0], $
        [ 68, 115, 181,   0], $
        [ 69, 129, 199,   0], $
        [ 70, 148, 222,   0], $
        [ 71, 161, 227,   7], $
        [ 72, 169, 224,  18], $
        [ 73, 177, 222,  29], $
        [ 74, 180, 219,  39], $
        [ 75, 186, 217,  50], $
        [ 76, 191, 214,  60], $
        [ 77, 195, 212,  70], $
        [ 78, 198, 209,  77], $
        [ 79, 201, 207,  87], $
        [ 80, 202, 204,  96], $
        [ 81, 201, 200, 101], $
        [ 82, 194, 189,  97], $
        [ 83, 189, 182,  94], $
        [ 84, 181, 170,  91], $
        [ 85, 176, 163,  88], $
        [ 86, 168, 153,  84], $
        [ 87, 161, 143,  80], $
        [ 88, 156, 135,  78], $
        [ 89, 148, 126,  74], $
        [ 90, 143, 118,  71], $
        [ 91, 138, 112,  70], $
        [ 92, 138, 112,  81], $
        [ 93, 135, 112,  93], $
        [ 94, 133, 113, 106], $
        [ 95, 133, 115, 121], $
        [ 96, 128, 114, 133], $
        [ 97, 125, 115, 145], $
        [ 98, 122, 117, 161], $
        [ 99, 116, 117, 173], $
        [100, 109, 117, 189], $
        [101, 103, 119, 201]]
end

function _$ctss$_peak_values
    compile_opt hidden, idl2, logical_predicate
    return, [ $
        [ 76, 150, 150, 150], $
        [ 77, 255, 170,   0], $
        [ 85, 255, 170,   0], $
        [ 93, 168, 112,   0], $
        [101,   0, 100,   0], $
        [109, 112, 168,   0], $
        [117, 205, 245, 122], $
        [125, 205, 205, 102], $
        [133, 137, 112,  68], $
        [141, 115,  76,   0], $
        [149, 115,  76,   0], $
        [157, 115,  76,   0], $
        [158, 150, 150, 150]]
end

function _$ctss$_end_values
    compile_opt hidden, idl2, logical_predicate
    return, [ $
        [124, 150, 150, 150], $
        [125, 110,  70,  45], $
        [133, 156, 132,  72], $
        [141, 115, 115,   0], $
        [149,  76, 115,   0], $
        [155, 168, 168,   0]]
end

;;
;; Maskenummer og RGB verdi for bruk på Landsat - vekstsesong Svalbard
;;
;; 1: - Ingen maske - putt inn vekstsesong data her
;;
;; 370 221 237 255      : Sea
;;
;; 371 0 92 230         : Lake/river 
;;
;; 374 150 150 150      : Moraine
;;
;; 375 100 100 100      : River gravel
;;
;; 380 255 255 255      : Glacier
;;
;; 384 215 194 166      : less vegetated (NDVI < 0.06)
;;
;; 385 170 170 170      : non-vegetated
;;
;;
;;
;;
function _$ctss$_mask
    compile_opt hidden, idl2, logical_predicate

    ct = bytarr(256, 3) ; r,g,b

    ct[200, *] = [221, 237, 255]                ; 370 - Sea
    ct[201, *] = [  0,  92, 230]                ; 371 - Lake/river
    ct[204, *] = [150, 150, 150]                ; 374 - Moraine
    ct[205, *] = [100, 100, 100]                ; 375 - River gravel
    ct[210, *] = [255, 255, 255]                ; 380 - Glacier
    ; ct[214, *] = [116, 116, 116]              ; 384 - Less vegetated (MODIS value)
    ct[214, *] = [215, 194, 166]                ; 384 - Less vegetated
    ct[215, *] = [170, 170, 170]                ; 385 - non-vegetated
    ct[220, *] = [123, 123, 123]

    return, ct
end

pro ct_sensyf_s2, onset=onset, peak=peak, gsend=gsend, ct=ct, load=load
    compile_opt idl2, logical_predicate


    ct = _$ctss$_mask()

    if keyword_set(onset) then begin
        values = _$ctss$_onset_values()
    endif else if keyword_set(peak) then begin
        values = _$ctss$_peak_values()
    endif else if keyword_set(gsend) then begin
        values = _$ctss$_end_values()
    endif else $
        message, 'One of keywords /ONSET, /PEAK or /GSEND must be set'

    _$ctss$_values, ct, values

    if keyword_set(load) then tvlct, ct
end



