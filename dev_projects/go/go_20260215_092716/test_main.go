package main_test

import (
	"testing"
)

// TestNewGoAgent verifica se NewGoAgent cria um novo GoAgent com a implementação do JiraClient correta
func TestNewGoAgent(t *testing.T) {
	client := &MockJiraClient{}
	ga := NewGoAgent(client)
	if ga.client != client {
		t.Errorf("Expected client to be %p, got %p", client, ga.client)
	}
}

// TestCreateIssue verifica se CreateIssue cria uma nova issue no Jira com valores válidos
func TestCreateIssue(t *testing.T) {
	client := &MockJiraClient{}
	ga := NewGoAgent(client)

	err := ga.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Expected CreateIssue to be successful, got error: %v", err)
	}
}

// TestCreateIssueError verifica se CreateIssue retorna um erro quando o JiraClient falha
func TestCreateIssueError(t *testing.T) {
	client := &MockJiraClient{
		CreateIssue: func(summary string, description string) error {
			return fmt.Errorf("Failed to create issue")
		},
	}

	ga := NewGoAgent(client)
	err := ga.CreateIssue("Test Issue", "This is a test issue.")
	if err == nil {
		t.Errorf("Expected CreateIssue to return an error, got success: %v", err)
	}
}