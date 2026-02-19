package main_test

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of GoAgentJiraClient
func TestCreateIssue(t *testing.T) {
	jira := GoAgentJiraClient{}

	// Test case 1: Success with valid inputs
	err := jira.CreateIssue("Teste de Issue", "Descrição do teste")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}

	// Test case 2: Error due to invalid input (empty title)
	err = jira.CreateIssue("", "Descrição do teste")
	if err == nil {
		t.Errorf("Expected an error, got none")
	}
}