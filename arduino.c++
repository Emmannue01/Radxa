#include <EEPROM.h>
#include <math.h> // Para usar sqrt()

const int NUM_TRANSDUCERS = 5;
const int transducerPins[NUM_TRANSDUCERS] = {A0, A1, A2, A3, A4};

// Cada transductor tiene su propio rango
float rangoTotalMM[NUM_TRANSDUCERS] = {25.0, 25.0, 25.0, 25.0, 25.0};
const float V_REF = 5.0;
const int ADC_RESOLUTION = 1024;

// Valores de calibración por defecto
int adcMin[NUM_TRANSDUCERS] = {100, 100, 100, 100, 100};
int adcMax[NUM_TRANSDUCERS] = {950, 950, 950, 950, 950};

const unsigned long INTERVAL = 100;
unsigned long previousMillis = 0;
const int NUM_SAMPLES = 10;

int readings[NUM_TRANSDUCERS][NUM_SAMPLES];
int readIndex[NUM_TRANSDUCERS] = {0, 0, 0, 0, 0};
long total[NUM_TRANSDUCERS] = {0, 0, 0, 0, 0};
int average[NUM_TRANSDUCERS] = {0, 0, 0, 0, 0};

// Nuevo: Array para saber qué transductores están habilitados para enviar datos
bool transducerEnabled[NUM_TRANSDUCERS] = {false, false, false, false, false};

// --- Configuración de EEPROM ---
const int EEPROM_ADDR_START = 0;
const byte EEPROM_VERSION = 0x03; // Versión incrementada por el cambio en la estructura de datos (añadimos rangos)

void setup() {
  Serial.begin(9600);
  analogReference(DEFAULT);
  
  // Configurar pines con resistencia PULL-DOWN interna para evitar lecturas flotantes.
  // Si un pin no está conectado, leerá un valor cercano a 0.
  for(int i = 0; i < NUM_TRANSDUCERS; i++) {
    pinMode(transducerPins[i], INPUT_PULLUP); // Se usa PULLUP y se invierte la lógica, es más estable.
    for(int j = 0; j < NUM_SAMPLES; j++) {
      readings[i][j] = 0;
    }
  }
 
  // Intentar cargar la calibración desde la EEPROM
  if (!loadCalibrationFromEEPROM()) {
    // Si falla, ofrecer calibración manual
    promptForCalibration();
  } else {
    // Mostrar valores cargados
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
    bool first_item = true; // Para controlar las comas
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
      // Solo procesar y enviar si el transductor está habilitado
      if (transducerEnabled[i]) {
        if (!first_item) {
          Serial.print(F(",")); // Separador
        }
        int adc = readFilteredADC(i, transducerPins[i]);
        float mm = adcToMM(adc, i);
        Serial.print(F("Pot")); Serial.print(i + 1);
        Serial.print(F(":"));
        Serial.print(mm, 3);
        first_item = false;
      }
    }
    // Solo enviar una nueva línea si se envió al menos un dato
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

// --- Funciones de lectura y conversión ---

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
  // Usar directamente los arrays globales
  if (adcMax[transducerIndex] == adcMin[transducerIndex]) {
    // Evitar división por cero
    return 0;
  }
  
  float normalized = (float)(adcValue - adcMin[transducerIndex]) / 
                    (float)(adcMax[transducerIndex] - adcMin[transducerIndex]);
  float mm = normalized * rangoTotalMM[transducerIndex];
  
  // Limitar valores
  if (mm < 0) mm = 0;
  if (mm > rangoTotalMM[transducerIndex]) mm = rangoTotalMM[transducerIndex];
  
  return mm;
}

// --- Funciones de calibración ---

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
  
  // Paso 1: 0mm
  Serial.print(F("PASO 1: Coloca TRANSDUCTOR ")); Serial.print(index + 1); Serial.println(F(" en 0mm"));
  Serial.println(F("        Presiona ENTER..."));
  waitForEnter();
  
  adcMin[index] = calibratePosition(transducerPins[index], "0mm");
  
  Serial.print(F("✓ ")); Serial.print(transducerName); Serial.print(F(" Mínimo (0mm): ADC = "));
  Serial.println(adcMin[index]);
  Serial.println();
  delay(1000);
  
  // Paso 2: Rango máximo
  Serial.print(F("PASO 2: Coloca TRANSDUCTOR ")); Serial.print(index + 1); Serial.print(F(" en "));
  Serial.print(rangoTotalMM[index]); Serial.println(F("mm (rango máximo)"));
  Serial.println(F("        Presiona ENTER..."));
  waitForEnter();
  
  char rangeStr[10];
  dtostrf(rangoTotalMM[index], 4, 1, rangeStr); // Convert float to string
  strcat(rangeStr, "mm");
  adcMax[index] = calibratePosition(transducerPins[index], rangeStr);
  
  Serial.print(F("✓ ")); Serial.print(transducerName); Serial.print(F(" Máximo: ADC = "));
  Serial.println(adcMax[index]);
  Serial.println();

  // *** SOLUCIÓN: Detectar y corregir inversión ***
  // Si el valor mínimo es mayor que el máximo, los intercambiamos.
  if (adcMin[index] > adcMax[index]) {
    Serial.println(F("ℹ  Valores invertidos detectados. Corrigiendo automáticamente..."));
    int temp = adcMin[index];
    adcMin[index] = adcMax[index];
    adcMax[index] = temp;
    Serial.print(F("✓  Nuevos valores: Min=")); Serial.print(adcMin[index]);
    Serial.print(F(", Max=")); Serial.println(adcMax[index]);
  }
  
  // Verificar calibración
  if (!verifyCalibration(index)) {
    Serial.println(F("⚠ Calibración inválida. Repite el proceso."));
    adcMin[index] = 100;  // Valores por defecto
    adcMax[index] = 950;
  } else {
    // Mostrar diferencia
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
  
  // Tomar lecturas
  for(int i = 0; i < numReadings; i++) {
    readingsArray[i] = analogRead(pin);
    sum += readingsArray[i];
    delay(20);
  }
  
  // Calcular promedio
  int avg = sum / numReadings;
  
  // Calcular desviación estándar para verificar estabilidad
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
  
  if (stdDev > 10) { // Si hay mucha variación
    Serial.println(F("⚠ Advertencia: Lecturas inestables. Reposiciona el transductor."));
  }
  
  // *** NUEVA LÓGICA: Encontrar la moda (valor más frecuente) en lugar del promedio ***
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

  // Si la moda es muy diferente del promedio, podría ser un error. En ese caso, usar el promedio.
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
    
    // Limpiar buffer
    delay(50);
    while (Serial.available() > 0) Serial.read();

    if (cmd >= '1' && cmd <= '5') {
      calibrateSingleTransducer(cmd - '1');
    } else if (cmd == 'S' || cmd == 's') {
      break; // Salir del bucle de calibración
    } else {
      Serial.println(F("Opción no válida. Inténtalo de nuevo."));
    }
  }

  // Guardar los nuevos valores en la EEPROM
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

// --- Funciones de utilidad ---

void waitForEnter() {
  while (Serial.available() > 0) Serial.read(); // Limpiar buffer
  
  Serial.println(F("Presiona ENTER para continuar..."));
  while (true) {
    if (Serial.available() > 0) {
      char c = Serial.read();
      if (c == '\n' || c == '\r') {
        break;
      }
    }
  }
  // Limpiar cualquier carácter restante
  while (Serial.available() > 0) Serial.read();
}

void handleRangeCommand() {
  delay(50); // Espera para que llegue el resto del comando
  String input = Serial.readStringUntil('\n');
  input.trim();
  
  // Buscar la coma
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

// --- Funciones de EEPROM ---

void saveCalibrationToEEPROM() {
  int addr = EEPROM_ADDR_START;
  EEPROM.update(addr, EEPROM_VERSION); // Usar update para escribir solo si el valor cambia
  addr += sizeof(byte);

  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    EEPROM.put(addr, adcMin[i]);
    addr += sizeof(int);
  }
  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    EEPROM.put(addr, adcMax[i]);
    addr += sizeof(int);
  }
  // Guardar también los rangos
  for (int i = 0; i < NUM_TRANSDUCERS; i++) {
    EEPROM.put(addr, rangoTotalMM[i]);
    addr += sizeof(float);
  }
  Serial.println(F("✓ Calibración guardada en memoria permanente (EEPROM)."));
}

bool loadCalibrationFromEEPROM() {
  int addr = EEPROM_ADDR_START;
  
  // Verificar si la EEPROM está vacía o corrupta
  byte version = EEPROM.read(addr);
  
  // Serial.print(F("Versión en EEPROM: 0x"));
  // Serial.println(version, HEX);
  // Serial.print(F("Versión esperada: 0x"));
  // Serial.println(EEPROM_VERSION, HEX);
  
  if (version == 0xFF) { // EEPROM vacía
    Serial.println(F("! EEPROM vacía. Usando valores por defecto."));
    return false; // No se cargó nada, se usarán los defaults
  }
  
  if (version == EEPROM_VERSION) {
    Serial.println(F("✓ Versión de calibración compatible"));
    addr += sizeof(byte);
    
    // Cargar valores
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
    
    // Verificar todos los transductores
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
      // Restaurar valores por defecto
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