<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Função para conectar ao banco de dados
function connectToDatabase() {
    $dsn = "mysql:host=localhost;dbname=test";
    $username = "root";
    $password = "";
    try {
        return new PDO($dsn, $username, $password);
    } catch (PDOException $e) {
        die("Connection failed: " . $e->getMessage());
    }
}

// Função para inserir um novo registro no banco de dados
function insertRecord($pdo, $data) {
    $query = "INSERT INTO users (name, email) VALUES (:name, :email)";
    $stmt = $pdo->prepare($query);
    $stmt->execute([
        'name' => $data['name'],
        'email' => $data['email']
    ]);
}

// Função para listar todos os registros do banco de dados
function listRecords($pdo) {
    $query = "SELECT * FROM users";
    $stmt = $pdo->prepare($query);
    $stmt->execute();
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

// Função principal
function main() {
    // Conectar ao banco de dados
    $pdo = connectToDatabase();

    // Inserir um novo registro
    $data = ['name' => 'John Doe', 'email' => 'john.doe@example.com'];
    insertRecord($pdo, $data);

    // Listar todos os registros
    $records = listRecords($pdo);
    print_r($records);
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}