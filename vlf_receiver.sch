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
L vlf_receiver:LMP7721 U1
U 1 1 606EE371
P 4400 3800
F 0 "U1" H 4400 4215 50  0000 C CNN
F 1 "LMP7721" H 4400 4124 50  0000 C CNN
F 2 "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm" H 4400 3450 50  0001 C CNN
F 3 "https://www.ti.com/lit/ds/symlink/lmp7721.pdf" H 3700 3850 50  0001 C CNN
F 4 "X" H 4400 3150 50  0001 C CNN "Spice_Primitive"
F 5 "LMP7721" H 4400 3250 50  0001 C CNN "Spice_Model"
F 6 "Y" H 4400 3050 50  0001 C CNN "Spice_Netlist_Enabled"
F 7 "lmp7721.scp" H 4400 3350 50  0001 C CNN "Spice_Lib_File"
	1    4400 3800
	1    0    0    -1  
$EndComp
$Comp
L power:GND #PWR0101
U 1 1 606F26F7
P 3900 4050
F 0 "#PWR0101" H 3900 3800 50  0001 C CNN
F 1 "GND" V 3905 3922 50  0000 R CNN
F 2 "" H 3900 4050 50  0001 C CNN
F 3 "" H 3900 4050 50  0001 C CNN
	1    3900 4050
	1    0    0    -1  
$EndComp
$Comp
L power:+5V #PWR0102
U 1 1 606F2DD1
P 5000 3850
F 0 "#PWR0102" H 5000 3700 50  0001 C CNN
F 1 "+5V" V 5015 3978 50  0000 L CNN
F 2 "" H 5000 3850 50  0001 C CNN
F 3 "" H 5000 3850 50  0001 C CNN
	1    5000 3850
	0    1    1    0   
$EndComp
Wire Wire Line
	3900 3850 4000 3850
Wire Wire Line
	4800 3850 5000 3850
NoConn ~ 4800 3950
Wire Wire Line
	4000 3750 3900 3750
Wire Wire Line
	3900 3750 3900 3300
Wire Wire Line
	3900 3300 4400 3300
Wire Wire Line
	4900 3650 4800 3650
Wire Wire Line
	4800 3750 4900 3750
Wire Wire Line
	4900 3750 4900 3650
Connection ~ 4900 3650
$Comp
L Reference_Voltage:TLE2426xLP U2
U 1 1 606F2F33
P 6750 3600
F 0 "U2" H 6750 3967 50  0000 C CNN
F 1 "TLE2426xLP" H 6750 3876 50  0000 C CNN
F 2 "Package_TO_SOT_THT:TO-92_Inline" H 6750 3200 50  0001 C CIN
F 3 "http://www.ti.com/lit/ds/symlink/tle2426.pdf" H 5350 4450 50  0001 C CIN
F 4 "X" H 6750 3600 50  0001 C CNN "Spice_Primitive"
F 5 "TLE2426x" H 6750 3600 50  0001 C CNN "Spice_Model"
F 6 "Y" H 6750 3600 50  0001 C CNN "Spice_Netlist_Enabled"
F 7 "tle2426x.scp" H 6750 3600 50  0001 C CNN "Spice_Lib_File"
	1    6750 3600
	1    0    0    -1  
$EndComp
$Comp
L power:GND #PWR0103
U 1 1 606F3E69
P 6750 4050
F 0 "#PWR0103" H 6750 3800 50  0001 C CNN
F 1 "GND" V 6755 3922 50  0000 R CNN
F 2 "" H 6750 4050 50  0001 C CNN
F 3 "" H 6750 4050 50  0001 C CNN
	1    6750 4050
	1    0    0    -1  
$EndComp
$Comp
L power:+5V #PWR0104
U 1 1 606F45F5
P 6150 3600
F 0 "#PWR0104" H 6150 3450 50  0001 C CNN
F 1 "+5V" V 6165 3728 50  0000 L CNN
F 2 "" H 6150 3600 50  0001 C CNN
F 3 "" H 6150 3600 50  0001 C CNN
	1    6150 3600
	0    -1   -1   0   
$EndComp
Wire Wire Line
	6150 3600 6350 3600
Wire Wire Line
	6750 4050 6750 3900
$Comp
L power:+2V5 #PWR0105
U 1 1 606F505D
P 7350 3600
F 0 "#PWR0105" H 7350 3450 50  0001 C CNN
F 1 "+2V5" V 7365 3728 50  0000 L CNN
F 2 "" H 7350 3600 50  0001 C CNN
F 3 "" H 7350 3600 50  0001 C CNN
	1    7350 3600
	0    1    1    0   
$EndComp
Wire Wire Line
	7150 3600 7350 3600
Wire Wire Line
	4900 3300 4900 3650
$Comp
L Device:R R?
U 1 1 606F7F56
P 4100 3100
F 0 "R?" V 3893 3100 50  0000 C CNN
F 1 "100k" V 3984 3100 50  0000 C CNN
F 2 "Resistor_SMD:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder" V 4030 3100 50  0001 C CNN
F 3 "~" H 4100 3100 50  0001 C CNN
	1    4100 3100
	0    1    1    0   
$EndComp
$Comp
L Device:R R?
U 1 1 606F8F65
P 4700 3100
F 0 "R?" V 4493 3100 50  0000 C CNN
F 1 "10k" V 4584 3100 50  0000 C CNN
F 2 "Resistor_SMD:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder" V 4630 3100 50  0001 C CNN
F 3 "~" H 4700 3100 50  0001 C CNN
	1    4700 3100
	0    1    1    0   
$EndComp
$Comp
L power:+2V5 #PWR?
U 1 1 606F940E
P 5000 3100
F 0 "#PWR?" H 5000 2950 50  0001 C CNN
F 1 "+2V5" V 5015 3228 50  0000 L CNN
F 2 "" H 5000 3100 50  0001 C CNN
F 3 "" H 5000 3100 50  0001 C CNN
	1    5000 3100
	0    1    1    0   
$EndComp
Wire Wire Line
	4850 3100 5000 3100
Wire Wire Line
	4250 3100 4400 3100
Wire Wire Line
	4400 3300 4400 3100
Connection ~ 4400 3300
Wire Wire Line
	4400 3300 4900 3300
Connection ~ 4400 3100
Wire Wire Line
	4400 3100 4550 3100
Wire Wire Line
	3900 4050 3900 3850
Wire Wire Line
	4000 3950 3800 3950
Wire Wire Line
	3800 3950 3800 3100
Wire Wire Line
	3800 3100 3950 3100
$EndSCHEMATC
