# Optional Linux amd64 worker; matching browser distribution, no host data or credentials.
FROM mcr.microsoft.com/playwright:v1.64.0-noble@sha256:bc72a8df40831ded821e3cbc79c318c21b44d6e51dff9fd89ace7a8249c5b462
WORKDIR /opt/evident-browser
RUN npm install --ignore-scripts --no-audit --no-fund playwright@1.64.0
COPY server.js ./server.js
USER pwuser
ENTRYPOINT ["node", "/opt/evident-browser/server.js"]
CMD ["9777"]
