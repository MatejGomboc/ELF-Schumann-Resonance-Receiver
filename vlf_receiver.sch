EESchema Schematic File Version 4
EELAYER 30 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 1 1
Title ""
Date ""
Rev ""
Comp ""
Comment1 ""
Comment2 ""
Comment3 ""
Comment4 ""
$EndDescr
$Comp
L vlf_receiver:LMP7721 U?
U 1 1 606EE371
P 4400 2950
F 0 "U?" H 4400 3365 50  0000 C CNN
F 1 "LMP7721" H 4400 3274 50  0000 C CNN
F 2 "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm" H 4400 2600 50  0001 C CNN
F 3 "https://www.ti.com/lit/ds/symlink/lmp7721.pdf" H 3700 3000 50  0001 C CNN
F 4 "X" H 4400 2300 50  0001 C CNN "Spice_Primitive"
F 5 "LMP7721" H 4400 2400 50  0001 C CNN "Spice_Model"
F 6 "Y" H 4400 2200 50  0001 C CNN "Spice_Netlist_Enabled"
F 7 "lmp7721.scp" H 4400 2500 50  0001 C CNN "Spice_Lib_File"
	1    4400 2950
	1    0    0    -1  
$EndComp
$Comp
L power:GND #PWR?
U 1 1 606F26F7
P 3850 3000
F 0 "#PWR?" H 3850 2750 50  0001 C CNN
F 1 "GND" V 3855 2872 50  0000 R CNN
F 2 "" H 3850 3000 50  0001 C CNN
F 3 "" H 3850 3000 50  0001 C CNN
	1    3850 3000
	0    1    1    0   
$EndComp
$Comp
L power:+5V #PWR?
U 1 1 606F2DD1
P 5000 3000
F 0 "#PWR?" H 5000 2850 50  0001 C CNN
F 1 "+5V" V 5015 3128 50  0000 L CNN
F 2 "" H 5000 3000 50  0001 C CNN
F 3 "" H 5000 3000 50  0001 C CNN
	1    5000 3000
	0    1    1    0   
$EndComp
Wire Wire Line
	3850 3000 4000 3000
Wire Wire Line
	4800 3000 5000 3000
NoConn ~ 4800 3100
Wire Wire Line
	4000 2900 3850 2900
Wire Wire Line
	3850 2900 3850 2400
Wire Wire Line
	3850 2400 4900 2400
Wire Wire Line
	4900 2400 4900 2800
Wire Wire Line
	4900 2800 4800 2800
Wire Wire Line
	4800 2900 4900 2900
Wire Wire Line
	4900 2900 4900 2800
Connection ~ 4900 2800
$EndSCHEMATC
