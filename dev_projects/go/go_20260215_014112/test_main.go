package main_test

import (
	"testing"
)

// TestNewGoAgent creates a new instance of GoAgent and verifies its creation
func TestNewGoAgent(t *testing.T) {
	client := &MockJiraClient{}
	goa := NewGoAgent(client)
	if goa == nil {
		t.Errorf("Failed to create GoAgent instance")
	}
}

// TestCreateIssue tests the CreateIssue method with valid inputs
func TestCreateIssue(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("New Feature Request", "Implement a new feature for the application.")
	if err != nil {
		t.Errorf("Error creating issue: %v", err)
	}
}

// TestCreateIssueWithError tests the CreateIssue method with invalid inputs
func TestCreateIssueWithError(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("", "Implement a new feature for the application.")
	if err == nil {
		t.Errorf("Expected error, but got none")
	}
}

// TestCreateIssueWithEdgeCases tests the CreateIssue method with edge cases
func TestCreateIssueWithEdgeCases(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("New Feature Request", "")
	if err == nil {
		t.Errorf("Expected error, but got none")
	}
}

// MockJiraClient is a mock implementation of JiraClient
type MockJiraClient struct{}

func (m *MockJiraClient) CreateIssue(title string, description string) error {
	fmt.Printf("Creating issue '%s' with description:\n%s\n", title, description)
	return nil
}