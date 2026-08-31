const { Client } = require("pg");
const client = new Client({
  host: "127.0.0.1",
  port: 5432,
  user: "postgres",
  password: "postgres",
  database: "estou_aqui"
});
client.connect()
  .then(() => console.log("SUCESSO"))
  .catch(e => console.error("ERRO:", e.message));
