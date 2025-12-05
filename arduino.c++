const int TRANS1_PIN = A0;
const int TRANS2_PIN = A1;
const int TRANS3_PIN = A2;
const int TRANS4_PIN = A3;
const float RANGO_TOTAL_MM = 25.0;
const float V_REF = 5.0;
const int ADC_RESOLUTION = 1024;
int ADC_MIN_T1 = 0;
int ADC_MAX_T1 = 1023;
int ADC_MIN_T2 = 0;
int ADC_MAX_T2 = 1023;
int ADC_MIN_T3 = 0;
int ADC_MAX_T3 = 1023;
int ADC_MIN_T4 = 0;
int ADC_MAX_T4 = 1023;
const unsigned long INTERVAL = 100;
unsigned long previousMillis = 0;
const int NUM_SAMPLES = 10;
int readings[4][NUM_SAMPLES];
int readIndex[4] = {0, 0, 0, 0};
long total[4] = {0, 0, 0, 0};
int average[4] = {0, 0, 0, 0};
bool isCalibrated = false;

void setup() {
  Serial.begin(9600);
  analogReference(DEFAULT);
  pinMode(TRANS1_PIN, INPUT);
  pinMode(TRANS2_PIN, INPUT);
  pinMode(TRANS3_PIN, INPUT);
  pinMode(TRANS4_PIN, INPUT);
  for(int i = 0; i < 4; i++) {
    for(int j = 0; j < NUM_SAMPLES; j++) {
      readings[i][j] = 0;
    }
  }
  Serial.println("========================================");
  Serial.println(" SISTEMA DE MONITOREO DE DEFORMACIONES");
  Serial.println(" Transductores Potenciométricos 2kΩ");
  Serial.println(" Precisión: ±0.005%");
  Serial.println("========================================");
  Serial.println();
  Serial.println("Rango: 0 a 25mm");
  Serial.println("Resolución: ~0.024mm/paso");
  Serial.println("Calibración: Individual por sensor");
  Serial.println();
  delay(1000);
  Serial.println("¿Deseas calibrar? (Envía 'C' en 5 segundos)");
  unsigned long startWait = millis();
  while(millis() - startWait < 5000) {
    if(Serial.available() > 0) {
      char cmd = Serial.read();
      if(cmd == 'C' || cmd == 'c') {
        calibrateTransducers();
        break;
      }
    }
  }
  Serial.println();
  Serial.println("Sistema iniciado - Enviando datos en mm...");
  Serial.println("========================================");
  Serial.println();
  delay(500);
}

void loop() {
  unsigned long currentMillis = millis();
  
  if (currentMillis - previousMillis >= INTERVAL) {
    previousMillis = currentMillis;
    int adc1 = readFilteredADC(0, TRANS1_PIN);
    int adc2 = readFilteredADC(1, TRANS2_PIN);
    int adc3 = readFilteredADC(2, TRANS3_PIN);
    int adc4 = readFilteredADC(3, TRANS4_PIN);
    float mm1 = adcToMM(adc1, ADC_MIN_T1, ADC_MAX_T1);
    float mm2 = adcToMM(adc2, ADC_MIN_T2, ADC_MAX_T2);
    float mm3 = adcToMM(adc3, ADC_MIN_T3, ADC_MAX_T3);
    float mm4 = adcToMM(adc4, ADC_MIN_T4, ADC_MAX_T4);
    Serial.print("P1:");
    Serial.print(mm1, 3);
    Serial.print(",P2:");
    Serial.print(mm2, 3);
    Serial.print(",P3:");
    Serial.print(mm3, 3);
    Serial.print(",P4:");
    Serial.println(mm4, 3);
  }
  if(Serial.available() > 0) {
    char cmd = Serial.read();
    if(cmd == 'C' || cmd == 'c') {
      calibrateTransducers();
    }
  }
}

int readFilteredADC(int transducer, int pin) {
  int newValue = analogRead(pin);
  total[transducer] -= readings[transducer][readIndex[transducer]];
  readings[transducer][readIndex[transducer]] = newValue;
  total[transducer] += newValue;
  readIndex[transducer] = (readIndex[transducer] + 1) % NUM_SAMPLES;
  average[transducer] = total[transducer] / NUM_SAMPLES;
  return average[transducer];
}

float adcToMM(int adcValue, int adcMin, int adcMax) {
  float normalized = (float)(adcValue - adcMin) / (float)(adcMax - adcMin);
  float mm = normalized * RANGO_TOTAL_MM;
  if(mm < 0) mm = 0;
  if(mm > RANGO_TOTAL_MM) mm = RANGO_TOTAL_MM;
  return mm;
}

void calibrateTransducers() {
  Serial.println();
  Serial.println("========================================");
  Serial.println("   CALIBRACIÓN INDIVIDUAL");
  Serial.println("========================================");
  Serial.println();
  Serial.println("Cada transductor se calibrará por separado");
  Serial.println();
  delay(2000);
  Serial.println("╔════════════════════════════════════╗");
  Serial.println("║     TRANSDUCTOR 1 (Pin A0)         ║");
  Serial.println("╚════════════════════════════════════╝");
  Serial.println();
  
  Serial.println("PASO 1: Coloca TRANSDUCTOR 1 en 0mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MIN_T1 = calibratePosition(TRANS1_PIN, "T1 - 0mm");
  Serial.print("✓ T1 Mínimo: ADC = ");
  Serial.println(ADC_MIN_T1);
  Serial.println();
  delay(1000);
  
  Serial.println("PASO 2: Coloca TRANSDUCTOR 1 en 25mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MAX_T1 = calibratePosition(TRANS1_PIN, "T1 - 25mm");
  Serial.print("✓ T1 Máximo: ADC = ");
  Serial.println(ADC_MAX_T1);
  Serial.println();
  delay(1500);
  Serial.println("╔════════════════════════════════════╗");
  Serial.println("║     TRANSDUCTOR 2 (Pin A1)         ║");
  Serial.println("╚════════════════════════════════════╝");
  Serial.println();
  
  Serial.println("PASO 1: Coloca TRANSDUCTOR 2 en 0mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MIN_T2 = calibratePosition(TRANS2_PIN, "T2 - 0mm");
  Serial.print("✓ T2 Mínimo: ADC = ");
  Serial.println(ADC_MIN_T2);
  Serial.println();
  delay(1000);
  
  Serial.println("PASO 2: Coloca TRANSDUCTOR 2 en 25mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MAX_T2 = calibratePosition(TRANS2_PIN, "T2 - 25mm");
  Serial.print("✓ T2 Máximo: ADC = ");
  Serial.println(ADC_MAX_T2);
  Serial.println();
  delay(1500);
  Serial.println("╔════════════════════════════════════╗");
  Serial.println("║     TRANSDUCTOR 3 (Pin A2)         ║");
  Serial.println("╚════════════════════════════════════╝");
  Serial.println();
  
  Serial.println("PASO 1: Coloca TRANSDUCTOR 3 en 0mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MIN_T3 = calibratePosition(TRANS3_PIN, "T3 - 0mm");
  Serial.print("✓ T3 Mínimo: ADC = ");
  Serial.println(ADC_MIN_T3);
  Serial.println();
  delay(1000);
  
  Serial.println("PASO 2: Coloca TRANSDUCTOR 3 en 25mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MAX_T3 = calibratePosition(TRANS3_PIN, "T3 - 25mm");
  Serial.print("✓ T3 Máximo: ADC = ");
  Serial.println(ADC_MAX_T3);
  Serial.println();
  delay(1500);
  Serial.println("╔════════════════════════════════════╗");
  Serial.println("║     TRANSDUCTOR 4 (Pin A3)         ║");
  Serial.println("╚════════════════════════════════════╝");
  Serial.println();
  
  Serial.println("PASO 1: Coloca TRANSDUCTOR 4 en 0mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MIN_T4 = calibratePosition(TRANS4_PIN, "T4 - 0mm");
  Serial.print("✓ T4 Mínimo: ADC = ");
  Serial.println(ADC_MIN_T4);
  Serial.println();
  delay(1000);
  
  Serial.println("PASO 2: Coloca TRANSDUCTOR 4 en 25mm");
  Serial.println("        Presiona ENTER...");
  waitForEnter();
  ADC_MAX_T4 = calibratePosition(TRANS4_PIN, "T4 - 25mm");
  Serial.print("✓ T4 Máximo: ADC = ");
  Serial.println(ADC_MAX_T4);
  Serial.println();
  delay(1500);
  Serial.println("========================================");
  Serial.println("   CALIBRACIÓN COMPLETADA");
  Serial.println("========================================");
  Serial.println();
  Serial.println("Valores de calibración:");
  Serial.println();
  Serial.println("// Transductor 1");
  Serial.print("int ADC_MIN_T1 = "); Serial.print(ADC_MIN_T1); Serial.println(";");
  Serial.print("int ADC_MAX_T1 = "); Serial.print(ADC_MAX_T1); Serial.println(";");
  Serial.println();
  
  Serial.println("// Transductor 2");
  Serial.print("int ADC_MIN_T2 = "); Serial.print(ADC_MIN_T2); Serial.println(";");
  Serial.print("int ADC_MAX_T2 = "); Serial.print(ADC_MAX_T2); Serial.println(";");
  Serial.println();
  
  Serial.println("// Transductor 3");
  Serial.print("int ADC_MIN_T3 = "); Serial.print(ADC_MIN_T3); Serial.println(";");
  Serial.print("int ADC_MAX_T3 = "); Serial.print(ADC_MAX_T3); Serial.println(";");
  Serial.println();
  
  Serial.println("// Transductor 4");
  Serial.print("int ADC_MIN_T4 = "); Serial.print(ADC_MIN_T4); Serial.println(";");
  Serial.print("int ADC_MAX_T4 = "); Serial.print(ADC_MAX_T4); Serial.println(";");
  Serial.println();
  
  Serial.println("Copia estos valores al código (líneas 28-43)");
  Serial.println("para no recalibrar cada vez.");
  Serial.println("========================================");
  Serial.println();
  isCalibrated = true;
  delay(2000);
}

int calibratePosition(int pin, const char* positionName) {
  Serial.print("Midiendo ");
  Serial.print(positionName);
  delay(500);
  const int numReadings = 100;
  long sum = 0;
  for(int i = 0; i < numReadings; i++) {
    sum += analogRead(pin);
    if(i % 20 == 0) Serial.print(".");
    delay(20);
  }
  Serial.println(" OK");
  int avg = sum / numReadings;
  return avg;
}

void waitForEnter() {
  while(Serial.available() > 0) Serial.read();
  while(Serial.available() == 0) {
    delay(100);
  }
  while(Serial.available() > 0) Serial.read();
}