# Dev
#
FROM node:22-alpine
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install
COPY . .
CMD [ "yarn", "dev", "--host"]


# Prod
#
# Stage 1
# FROM node:22-alpine AS build
# WORKDIR /app
# COPY package.json yarn.lock ./
# RUN yarn install
# COPY . .
# RUN yarn build

# Stage 2
# FROM nginx:stable-alpine
# COPY --from=build /app/build /usr/share/nginx/html
# EXPOSE 80
# CMD ["nginx", "-g", "daemon off;"]
