package main

import (
	"testing"
)

// TestNewJiraClient verifica se NewJiraClient cria uma nova instância corretamente
func TestNewJiraClient(t *testing.T) {
	client := NewJiraClient("your-client-id")
	if client == nil {
		t.Errorf("NewJiraClient returned nil")
	}
}

// TestCreateIssue verifica se CreateIssue cria um novo issue com sucesso
func TestCreateIssue(t *testing.T) {
	jc := NewJiraClient("your-client-id")

	err := jc.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("CreateIssue returned error: %v", err)
	}
}

// TestUpdateIssue verifica se UpdateIssue atualiza um existing issue com sucesso
func TestUpdateIssue(t *testing.T) {
	jc := NewJiraClient("your-client-id")

	err := jc.UpdateIssue("12345", "Feature Request Updated", "Implemented the new feature")
	if err != nil {
		t.Errorf("UpdateIssue returned error: %v", err)
	}
}

// TestDeleteIssue verifica se DeleteIssue deleta um existing issue com sucesso
func TestDeleteIssue(t *testing.T) {
	jc := NewJiraClient("your-client-id")

	err := jc.DeleteIssue("12345")
	if err != nil {
		t.Errorf("DeleteIssue returned error: %v", err)
	}
}

// TestCreateIssueError verifica se CreateIssue retorna um erro quando o cliente ID é vazio
func TestCreateIssueError(t *testing.T) {
	jc := NewJiraClient("")
	err := jc.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err == nil {
		t.Errorf("CreateIssue did not return an error when clientID is empty")
	}
}

// TestUpdateIssueError verifica se UpdateIssue retorna um erro quando o ID do issue é vazio
func TestUpdateIssueError(t *testing.T) {
	jc := NewJiraClient("your-client-id")

	err := jc.UpdateIssue("", "Feature Request Updated", "Implemented the new feature")
	if err == nil {
		t.Errorf("UpdateIssue did not return an error when issueID is empty")
	}
}

// TestDeleteIssueError verifica se DeleteIssue retorna um erro quando o ID do issue é vazio
func TestDeleteIssueError(t *testing.T) {
	jc := NewJiraClient("your-client-id")

	err := jc.DeleteIssue("")
	if err == nil {
		t.Errorf("DeleteIssue did not return an error when issueID is empty")
	}
}