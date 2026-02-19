<?php

use PHPUnit\Framework\TestCase;

class DatabaseTest extends TestCase {
    public function testConnectToDatabase() {
        $this->expectException(PDOException::class);
        connectToDatabase();
    }

    public function testInsertRecord() {
        $pdo = connectToDatabase();
        $data = ['name' => 'John Doe', 'email' => 'john.doe@example.com'];
        insertRecord($pdo, $data);

        // Verificar se o registro foi inserido corretamente
        $records = listRecords($pdo);
        $this->assertArrayHasKey('id', $records[0]);
    }

    public function testListRecords() {
        $pdo = connectToDatabase();
        $data = ['name' => 'John Doe', 'email' => 'john.doe@example.com'];
        insertRecord($pdo, $data);

        // Listar todos os registros
        $records = listRecords($pdo);
        $this->assertNotEmpty($records);
    }
}