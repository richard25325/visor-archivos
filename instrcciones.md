# Proyecto: Explorador y visor documental institucional

## 1. Objetivo

Desarrollar una aplicación de escritorio en Python que permita explorar automáticamente una carpeta documental y todas sus subcarpetas, identificar archivos, extraer sus metadatos y generar un índice jerárquico navegable por categorías, documentos, capítulos y subcapítulos.

La aplicación debe permitir consultar el contenido de cada documento mediante una vista previa integrada, sin necesidad de abrir Microsoft Word, Adobe Acrobat o Microsoft Excel.

## 2. Tecnologías

- **Python 3**
- **PySide6:** interfaz gráfica de escritorio.
- **PyMuPDF:** lectura, extracción de texto y visualización de PDF.
- **python-docx:** extracción de títulos, párrafos, tablas y contenido de Word.
- **openpyxl:** lectura de libros, hojas y datos de Excel.
- **SQLite:** almacenamiento local del índice y los metadatos para evitar analizar todos los archivos en cada inicio.
- **watchdog:** detección opcional de cambios en los archivos y carpetas.

La aplicación debe funcionar en Windows y poder empaquetarse como ejecutable.

## 3. Exploración automática de carpetas

- Permitir seleccionar una carpeta raíz.
- Recorrer recursivamente todas sus subcarpetas.
- Detectar documentos PDF, DOCX, XLSX y otros formatos que se incorporen posteriormente.
- Mostrar las carpetas y documentos respetando su jerarquía original.
- Identificar el código, título, tipo documental y versión cuando puedan extraerse.
- Utilizar el nombre y la ruta del archivo como datos de respaldo cuando no se detecten los metadatos.
- Detectar archivos nuevos, modificados o eliminados y actualizar el índice.
- Permitir actualizar manualmente el catálogo.

La carpeta raíz puede encontrarse en una carpeta local o en una carpeta sincronizada con OneDrive.

## 4. Índice jerárquico lateral

Crear una interfaz similar a un explorador documental, con un árbol expandible y contraíble.

La jerarquía debe incluir:

1. Carpetas y subcarpetas.
2. Categorías documentales, como procedimientos, formularios, instructivos, manuales y reglamentos, cuando corresponda.
3. Documentos identificados por su código y título.
4. Capítulos, apartados y subapartados detectados dentro de cada documento.

Ejemplo:

- Procedimientos
  - PR-001 — Control documental
    - 1. Objetivo
    - 2. Alcance
    - 3. Responsabilidades
    - 4. Desarrollo
      - 4.1 Recepción
      - 4.2 Gestión documental
        - 4.2.1 Verificación
        - 4.2.2 Aprobación
      - 4.3 Publicación
- Formularios
  - FO-001 — Registro de documentos

Los niveles de profundidad deben ser dinámicos, sin limitar la estructura a un número fijo de niveles.

## 5. Detección de apartados

### Word

- Detectar los estilos de título de Word: Título 1, Título 2, Título 3, etc.
- Identificar títulos numerados mediante patrones como `1.`, `1.1`, `4.2` y `4.2.1`.
- Extraer los párrafos, tablas e imágenes asociados a cada sección cuando sea técnicamente posible.
- Determinar el contenido de una sección hasta el siguiente título del mismo nivel o de un nivel superior.

### PDF

- Extraer texto por página.
- Identificar encabezados numerados y posibles títulos.
- Estimar la página inicial y final de cada apartado.
- Mostrar la página o el rango de páginas correspondiente.
- Contemplar que algunos PDF son escaneados y requieren OCR, funcionalidad que puede añadirse posteriormente.
- Aprovechar los marcadores internos del PDF cuando existan.

### Excel

- Identificar el libro y sus hojas.
- Mostrar las hojas como elementos navegables.
- Detectar tablas y encabezados cuando sea posible.
- Mostrar los datos seleccionados en una cuadrícula dentro de la aplicación.

La detección debe combinar estilos, numeración, estructura y reglas configurables. No debe asumir que todos los documentos están formateados de la misma manera.

## 6. Visor integrado

La ventana principal debe dividirse en dos paneles:

- **Panel izquierdo:** árbol de navegación y buscador.
- **Panel derecho:** información del documento y vista previa de su contenido.

Al seleccionar un documento, mostrar código, título, tipo, versión y ruta.

Al seleccionar un apartado, mostrar directamente su contenido sin abrir aplicaciones externas.

Comportamiento por formato:

- **PDF:** mostrar las páginas correspondientes mediante un visor integrado, con zoom y navegación.
- **Word:** mostrar los párrafos, títulos, tablas e imágenes de la sección seleccionada, conservando razonablemente el formato.
- **Excel:** mostrar las hojas y tablas en una cuadrícula.

Añadir una opción para abrir el archivo original con su aplicación predeterminada de Windows.

La vista previa debe ser de solo lectura y no modificar los archivos originales.

## 7. Búsqueda

Implementar búsqueda por:

- Código documental.
- Título.
- Nombre del archivo.
- Tipo documental.
- Texto extraído del contenido, cuando esté disponible.

Los resultados deben permitir navegar directamente al documento o apartado correspondiente.

## 8. Base de datos local

Utilizar SQLite para almacenar:

- Rutas de archivos.
- Nombre, extensión, tamaño y fecha de modificación.
- Código, título, versión y tipo documental detectados.
- Identificadores de carpetas y documentos.
- Jerarquía de apartados y subapartados.
- Número de página inicial y final cuando corresponda.
- Texto extraído para facilitar las búsquedas.
- Fecha del último análisis y estado de procesamiento.

La estructura de apartados debe admitir relaciones padre-hijo recursivas.

La base de datos es un índice auxiliar; los archivos originales permanecen en sus ubicaciones.

## 9. Interfaz y experiencia de usuario

- Diseño moderno, limpio y profesional.
- Interfaz en español.
- Árbol lateral expandible y contraíble.
- Iconos diferenciados para carpetas y tipos de archivos.
- Indicadores visuales del formato documental.
- Buscador de acceso rápido.
- Barra de estado con el progreso del análisis.
- Mensajes de error por archivo sin detener el procesamiento del resto.
- Opción para reindexar la biblioteca.
- Recordar la última carpeta raíz seleccionada.
- Soportar bibliotecas con una gran cantidad de documentos sin bloquear la interfaz.

El análisis de documentos debe ejecutarse en segundo plano para mantener la interfaz receptiva.

## 10. Arquitectura y calidad

Separar el proyecto en módulos:

- Interfaz gráfica.
- Exploración del sistema de archivos.
- Procesadores independientes para PDF, Word y Excel.
- Detector de títulos y apartados.
- Base de datos e indexación.
- Búsqueda.
- Visores de cada formato.
- Configuración de la aplicación.

Implementar manejo de errores, registros de actividad y procesamiento incremental. Evitar volver a analizar archivos que no hayan cambiado.

## 11. Alcance inicial y prioridades

Desarrollar primero una versión funcional que permita:

1. Seleccionar una carpeta raíz.
2. Recorrer todas sus subcarpetas.
3. Indexar PDF, DOCX y XLSX.
4. Extraer títulos y apartados.
5. Mostrar el índice jerárquico.
6. Seleccionar un apartado y ver su contenido en el panel derecho.
7. Buscar documentos.
8. Abrir el archivo original.
9. Guardar el índice en SQLite para reutilizarlo.

Dejar OCR, sincronización avanzada con Microsoft Graph, edición documental y formatos adicionales para futuras versiones.

**Criterio principal de aceptación:** el usuario debe poder seleccionar una carpeta de documentos institucionales, visualizar su estructura jerárquica automáticamente y navegar desde un apartado del índice hasta su contenido mediante una vista previa integrada, sin tener que abrir cada documento en su aplicación original.