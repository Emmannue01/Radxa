#include <EEPROM.h>
#include <math.h>

const int NUM_TRANSDUCERS = 5;
const int transducerPins[NUM_TRANSDUCERS] = {A0, A1, A2, A3, A4};

float rangoTotalMM[NUM_TRANSDUCERS] = {25.0, 25.0, 25.0, 25.0, 25.0};
const float V_REF = 5.0;
const int ADC_RESOLUTION = 1024;

int adcMin[NUM_TRANSDUCERS] = {100, 100, 100, 100, 100};
int adcMax[NUM_TRANSDUCERS] = {950, 950, 950, 950, 950};

const unsigned long INTERVAL = 100;
unsigned long previousMillis = 0;
const int NUM_SAMPLES = 10;

int readings[NUM_TRANSDUCERS][NUM_SAMPLES];
int readIndex[NUM_TRANSDUCERS] = {0, 0, 0, 0, 0};
long total[NUM_TRANSDUCERS] = {0, 0, 0, 0, 0};
int average[NUM_TRANSDUCERS] = {0, 0, 0, 0, 0};

bool transducerEnabled[NUM_TRANSDUCERS] = {false, false, false, false, false};

const int EEPROM_ADDR_START = 0;
const byte EEPROM_VERSION = 0x03;

void setup() {
  Serial.begin(9600);
  analogReference(DEFAULT);
  
  for(int i = 0; i < NUM_TRANSDUCERS; i++) {
    pinMode(transducerPins[i], INPUT_PULLUP);
    for(int j = 0; j < NUM_SAMPLES; j++) {
      readings[i][j] = 0;
    }
  }
 
  if (!loadCalibrationFromEEPROM()) {
    promptForCalibration();
  } else {
    Serial.println(F("\nValores de calibración cargados:"));
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
      Serial.print(F("T")); Serial.print(i + 1);
      Serial.print(F(": Min=")); Serial.print(adcMin[i]);
      Serial.print(F(" Max=")); Serial.print(adcMax[i]);
      Serial.print(F(" Rango=")); Serial.print(rangoTotalMM[i]); Serial.println(F("mm"));
    }
  }

  Serial.println();
  Serial.println(F("Sistema iniciado - Enviando datos en mm..."));
  Serial.println(F("========================================"));
  Serial.println();
  delay(500);
}

void loop() {
  unsigned long currentMillis = millis();
  
  if (currentMillis - previousMillis >= INTERVAL) {
    previousMillis = currentMillis;
    bool first_item = true;
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
      if (transducerEnabled[i]) {
        if (!first_item) {
          Serial.print(F(","));
        }
        int adc = readFilteredADC(i, transducerPins[i]);
        float mm = adcToMM(adc, i);
        Serial.print(F("Pot")); Serial.print(i + 1);
        Serial.print(F(":"));
        Serial.print(mm, 3);
        first_item = false;
      }
    }
    if (!first_item) {
      Serial.println();
    }
  }
  
  if(Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'C' || cmd == 'c') {
      calibrateTransducers();
    } else if (cmd == 'R' || cmd == 'r') {
      handleRangeCommand();
    } else if (cmd == 'E' || cmd == 'D') { // Comandos para Habilitar (E) o Deshabilitar (D)
      int index = Serial.parseInt();
      if (index > 0 && index <= NUM_TRANSDUCERS) {
        if (cmd == 'E') {
          transducerEnabled[index - 1] = true;
        } else { // cmd == 'D'
          transducerEnabled[index - 1] = false;
        }
      }
    }
  }
}


int readFilteredADC(int transducer, int pin) {
  int newValue = analogRead(pin);
  delay(1); // Pequeño delay para estabilizar lecturas consecutivas
  
  total[transducer] -= readings[transducer][readIndex[transducer]];
  readings[transducer][readIndex[transducer]] = newValue;
  total[transducer] += newValue;
  readIndex[transducer] = (readIndex[transducer] + 1) % NUM_SAMPLES;
  average[transducer] = total[transducer] / NUM_SAMPLES;
  
  return average[transducer];
}

float adcToMM(int adcValue, int transducerIndex) {
  if (adcMax[transducerIndex] == adcMin[transducerIndex]) {
    return 0;
  }
  
  float normalized = (float)(adcValue - adcMin[transducerIndex]) / 
                    (float)(adcMax[transducerIndex] - adcMin[transducerIndex]);
  float mm = normalized * rangoTotalMM[transducerIndex];
  
  if (mm < 0) mm = 0;
  if (mm > rangoTotalMM[transducerIndex]) mm = rangoTotalMM[transducerIndex];
  
  return mm;
}

void promptForCalibration() {
  Serial.println();
  delay(1000);
  Serial.println(F("¿Deseas calibrar? (Envía 'C' en 5 segundos)"));
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
}

void printCalibrationMenu() {
  Serial.println();
  Serial.println(F("========================================"));
  Serial.println(F("   MENÚ DE CALIBRACIÓN"));
  Serial.println(F("========================================"));
  Serial.println(F("Elige una opción:"));
  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    Serial.print(F("  "));
    Serial.print(i + 1);
    Serial.print(F(" - Calibrar Transductor "));
    Serial.println(i + 1);
  }
  Serial.println(F("  S - Salir y guardar"));
  Serial.print(F("Opción: "));
}

void calibrateSingleTransducer(int index) {
  char transducerName[4];
  sprintf(transducerName, "T%d", index + 1);

  Serial.println();
  Serial.println(F("╔════════════════════════════════════╗"));
  Serial.print(F("║     TRANSDUCTOR ")); Serial.print(index + 1); Serial.print(F(" (Pin A")); Serial.print(index); Serial.println(F(")         ║"));
  Serial.println(F("╚════════════════════════════════════╝"));
  Serial.println();
  
  Serial.print(F("PASO 1: Coloca TRANSDUCTOR ")); Serial.print(index + 1); Serial.println(F(" en 0mm"));
  Serial.println(F("        Presiona ENTER..."));
  waitForEnter();
  
  adcMin[index] = calibratePosition(transducerPins[index], "0mm");
  
  Serial.print(F("✓ ")); Serial.print(transducerName); Serial.print(F(" Mínimo (0mm): ADC = "));
  Serial.println(adcMin[index]);
  Serial.println();
  delay(1000);
  
  Serial.print(F("PASO 2: Coloca TRANSDUCTOR ")); Serial.print(index + 1); Serial.print(F(" en "));
  Serial.print(rangoTotalMM[index]); Serial.println(F("mm (rango máximo)"));
  Serial.println(F("        Presiona ENTER..."));
  waitForEnter();
  
  char rangeStr[10];
  dtostrf(rangoTotalMM[index], 4, 1, rangeStr);
  strcat(rangeStr, "mm");
  adcMax[index] = calibratePosition(transducerPins[index], rangeStr);
  
  Serial.print(F("✓ ")); Serial.print(transducerName); Serial.print(F(" Máximo: ADC = "));
  Serial.println(adcMax[index]);
  Serial.println();

  if (adcMin[index] > adcMax[index]) {
    Serial.println(F("ℹ  Valores invertidos detectados. Corrigiendo automáticamente..."));
    int temp = adcMin[index];
    adcMin[index] = adcMax[index];
    adcMax[index] = temp;
    Serial.print(F("✓  Nuevos valores: Min=")); Serial.print(adcMin[index]);
    Serial.print(F(", Max=")); Serial.println(adcMax[index]);
  }
  
  if (!verifyCalibration(index)) {
    Serial.println(F("⚠ Calibración inválida. Repite el proceso."));
    adcMin[index] = 100;
    adcMax[index] = 950;
  } else {
    int range = adcMax[index] - adcMin[index];
    Serial.print(F("Rango ADC: ")); Serial.println(range);
    Serial.print(F("Resolución: ")); Serial.print((float)range / rangoTotalMM[index], 3);
    Serial.println(F(" puntos ADC/mm"));
  }
  
  delay(1500);
}

int calibratePosition(int pin, const char* positionName) {
  Serial.print(F("Midiendo "));
  Serial.print(positionName);
  Serial.println(F("..."));
  
  const int numReadings = 100;
  long sum = 0;
  int readingsArray[numReadings];
  
  for(int i = 0; i < numReadings; i++) {
    readingsArray[i] = analogRead(pin);
    sum += readingsArray[i];
    delay(20);
  }
  
  int avg = sum / numReadings;
  
  long sumSqDiff = 0;
  for(int i = 0; i < numReadings; i++) {
    long diff = readingsArray[i] - avg;
    sumSqDiff += diff * diff;
  }
  int stdDev = sqrt(sumSqDiff / numReadings);
  
  Serial.print(F("✓ Valor ADC promedio: "));
  Serial.print(avg);
  Serial.print(F(" (Desviación: ±"));
  Serial.print(stdDev);
  Serial.println(F(")"));
  
  if (stdDev > 10) {
    Serial.println(F("⚠ Advertencia: Lecturas inestables. Reposiciona el transductor."));
  }
  
  int mode = 0;
  int maxCount = 0;
  for (int i = 0; i < numReadings; i++) {
    int count = 0;
    for (int j = 0; j < numReadings; j++) {
      if (readingsArray[j] == readingsArray[i]) {
        count++;
      }
    }
    if (count > maxCount) {
      maxCount = count;
      mode = readingsArray[i];
    }
  }

  if (abs(mode - avg) > stdDev * 2) {
    Serial.println(F("ℹ  Moda inconsistente, usando promedio para seguridad."));
    return avg;
  }

  Serial.print(F("✓ Valor más estable (moda): ")); Serial.println(mode);
  return mode;
}

bool verifyCalibration(int transducerIndex) {
  if (adcMin[transducerIndex] < 0 || adcMin[transducerIndex] > ADC_RESOLUTION) {
    Serial.print(F("! adcMin["));
    Serial.print(transducerIndex);
    Serial.println(F("] fuera de rango"));
    return false;
  }
  
  if (adcMax[transducerIndex] < 0 || adcMax[transducerIndex] > ADC_RESOLUTION) {
    Serial.print(F("! adcMax["));
    Serial.print(transducerIndex);
    Serial.println(F("] fuera de rango"));
    return false;
  }
  
  if (adcMax[transducerIndex] <= adcMin[transducerIndex]) {
    Serial.print(F("! adcMax["));
    Serial.print(transducerIndex);
    Serial.print(F("] ("));
    Serial.print(adcMax[transducerIndex]);
    Serial.print(F(") debe ser mayor que adcMin["));
    Serial.print(transducerIndex);
    Serial.print(F("] ("));
    Serial.print(adcMin[transducerIndex]);
    Serial.println(F(")"));
    return false;
  }
  
  return true;
}

void calibrateTransducers() {
  while (true) {
    printCalibrationMenu();
    while (Serial.available() == 0) { delay(100); }
    char cmd = Serial.read();
    Serial.println(cmd);
    
    delay(50);
    while (Serial.available() > 0) Serial.read();

    if (cmd >= '1' && cmd <= '5') {
      calibrateSingleTransducer(cmd - '1');
    } else if (cmd == 'S' || cmd == 's') {
      break;
    } else {
      Serial.println(F("Opción no válida. Inténtalo de nuevo."));
    }
  }

  saveCalibrationToEEPROM();

  Serial.println(F("========================================"));
  Serial.println(F("   CALIBRACIÓN COMPLETADA"));
  Serial.println(F("========================================"));
  Serial.println();
  Serial.println(F("Valores de calibración:"));
  Serial.println();
  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    Serial.print(F("Transductor ")); Serial.print(i + 1);
    Serial.print(F(": Min=")); Serial.print(adcMin[i]);
    Serial.print(F(", Max=")); Serial.print(adcMax[i]);
    Serial.print(F(", Rango=")); Serial.print(rangoTotalMM[i]); Serial.println(F("mm"));
  }
  
  Serial.println(F("\nValores guardados en EEPROM. No es necesario recalibrar al reiniciar."));
  Serial.println(F("========================================"));
  Serial.println();
  delay(2000);
}

void waitForEnter() {
  while (Serial.available() > 0) Serial.read();
  
  Serial.println(F("Presiona ENTER para continuar..."));
  while (true) {
    if (Serial.available() > 0) {
      char c = Serial.read();
      if (c == '\n' || c == '\r') {
        break;
      }
    }
  }
  while (Serial.available() > 0) Serial.read();
}

void handleRangeCommand() {
  delay(50);
  String input = Serial.readStringUntil('\n');
  input.trim();
  
  int commaIndex = input.indexOf(',');
  if (commaIndex > 0) {
    String indexStr = input.substring(0, commaIndex);
    String rangeStr = input.substring(commaIndex + 1);
    int index = indexStr.toInt() - 1;
    float newRange = rangeStr.toFloat();
    
    if (index >= 0 && index < NUM_TRANSDUCERS && newRange > 0) {
      rangoTotalMM[index] = newRange;
      saveCalibrationToEEPROM();
      Serial.print(F("✓ Rango T")); Serial.print(index + 1);
      Serial.print(F(" actualizado a ")); Serial.print(newRange); Serial.println(F("mm"));
    } else {
      Serial.println(F("Error: Índice o rango no válido"));
      Serial.println(F("Formato: R<index>,<range> (ej: R1,50.0)"));
    }
  } else {
    Serial.println(F("Error: Formato incorrecto"));
    Serial.println(F("Formato: R<index>,<range> (ej: R1,50.0)"));
  }
}

void saveCalibrationToEEPROM() {
  int addr = EEPROM_ADDR_START;
  EEPROM.update(addr, EEPROM_VERSION);
  addr += sizeof(byte);

  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    EEPROM.put(addr, adcMin[i]);
    addr += sizeof(int);
  }
  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    EEPROM.put(addr, adcMax[i]);
    addr += sizeof(int);
  }
  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    EEPROM.put(addr, rangoTotalMM[i]);
    addr += sizeof(float);
  }
  Serial.println(F("✓ Calibración guardada en memoria permanente (EEPROM)."));
}

bool loadCalibrationFromEEPROM() {
  int addr = EEPROM_ADDR_START;
  
  byte version = EEPROM.read(addr);
  
  if (version == 0xFF) {
    Serial.println(F("! EEPROM vacía. Usando valores por defecto."));
    return false;
  }
  
  if (version == EEPROM_VERSION) {
    Serial.println(F("✓ Versión de calibración compatible"));
    addr += sizeof(byte);
    
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
      EEPROM.get(addr, adcMin[i]);
      addr += sizeof(int);
    }
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
      EEPROM.get(addr, adcMax[i]);
      addr += sizeof(int);
    }
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
      EEPROM.get(addr, rangoTotalMM[i]);
      addr += sizeof(float);
    }
    
    bool allValid = true;
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
      if (!verifyCalibration(i)) {
        allValid = false;
      }
    }
    
    if (allValid) {
      Serial.println(F("✓ Calibración cargada y verificada exitosamente"));
      return true;
    } else {
      Serial.println(F("! Calibración en EEPROM inválida. Usando valores por defecto."));
      for (int i = 0; i < NUM_TRANSDUCERS; i++) {
        adcMin[i] = 100;
        adcMax[i] = 950;
        rangoTotalMM[i] = 25.0;
      }
      return false;
    }
  }
  
  Serial.println(F("! No se encontró calibración válida en EEPROM. Usando valores por defecto."));
  return false;
}