# Usar una imagen base oficial de Node.js
FROM node:14-alpine

# Establecer el directorio de trabajo en la imagen Docker
WORKDIR /asu-notifier

# Copiar el package.json y el package-lock.json para instalar las dependencias
COPY package*.json ./

# Instalar las dependencias
RUN npm install

# Copiar el resto de los archivos de la aplicación
COPY . .

# Comando para ejecutar la aplicación
CMD ["npm", "start"]
