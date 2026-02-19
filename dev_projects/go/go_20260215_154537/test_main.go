package main

import (
	"testing"
)

// MockJiraClient é uma implementação simulada da interface JiraClient
type MockJiraClient struct{}

func (m *MockJiraClient) CreateIssue(issue *Issue) error {
	if issue.Title == "" || issue.Body == "" {
		return fmt.Errorf("Title and Body cannot be empty")
	}
	fmt.Printf("Issue created: %s\n", issue.Title)
	return nil
}

func (m *MockJiraClient) UpdateIssue(issue *Issue) error {
	if issue.Title == "" || issue.Body == "" {
		return fmt.Errorf("Title and Body cannot be empty")
	}
	fmt.Printf("Issue updated: %s\n", issue.Title)
	return nil
}

// TestCreateIssue verifica se CreateIssue funciona corretamente
func TestCreateIssue(t *testing.T) {
	jiraClient := &MockJiraClient{}
	newIssue := Issue{
		ID:    "12345",
		Title: "Teste do Go Agent com Jira",
		Body:  "Este é um teste para integrar o Go Agent com o Jira.",
	}

	err := jiraClient.CreateIssue(&newIssue)
	if err != nil {
		t.Errorf("CreateIssue failed with error: %v", err)
	}
}

// TestUpdateIssue verifica se UpdateIssue funciona corretamente
func TestUpdateIssue(t *testing.T) {
	jiraClient := &MockJiraClient{}
	newIssue := Issue{
		ID:    "12345",
		Title: "Teste do Go Agent com Jira",
		Body:  "Este é um teste para integrar o Go Agent com o Jira.",
	}

	err := jiraClient.UpdateIssue(&newIssue)
	if err != nil {
		t.Errorf("UpdateIssue failed with error: %v", err)
	}
}