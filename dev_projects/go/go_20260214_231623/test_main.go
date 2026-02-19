package main

import (
	"testing"
)

// MockJiraClient é uma implementação simulada do JiraClient
type MockJiraClient struct{}

func (m *MockJiraClient) CreateIssue(issue *Issue) error {
	if issue.Title == "" || issue.Description == "" || issue.Status == "" {
		return fmt.Errorf("Issue deve ter todos os campos preenchidos")
	}
	return nil
}

// TestCreateIssueTest testa a função CreateIssue do JiraClient
func TestCreateIssueTest(t *testing.T) {
	jira := &MockJiraClient{}

	testCases := []struct {
		title    string
		description string
		status   string
	}{
		{"Teste Go Agent", "Integração com Jira", "Open"},
		{"", "Integração com Jira", "Open"},
		{"Teste Go Agent", "", "Open"},
		{"Teste Go Agent", "Integração com Jira", ""},
	}

	for _, tc := range testCases {
		newIssue := Issue{
			Title:    tc.title,
			Description: tc.description,
			Status:   tc.status,
		}
		err := jira.CreateIssue(&newIssue)
		if err != nil {
			t.Errorf("CreateIssue(%v) deve ter sucesso, mas retornou %v", newIssue, err)
		}
	}
}