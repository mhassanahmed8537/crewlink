FROM node:20-alpine

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8080/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
