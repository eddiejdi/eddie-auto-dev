package main

import (
	"testing"
	"time"
)

// JiraClientMock é uma implementação mock para JiraClient
type JiraClientMock struct{}

func (m *JiraClientMock) CreateIssue(title string, description string) error {
	if title == "" || description == "" {
		return fmt.Errorf("title e description devem ser não vazios")
	}
	return nil
}

func (m *JiraClientMock) UpdateIssue(issueID int, title string, description string) error {
	if issueID <= 0 {
		return fmt.Errorf("issueID deve ser maior que zero")
	}
	return nil
}

// TestGoAgentTest é um teste unitário para GoAgent
func TestGoAgentTest(t *testing.T) {
	jiraClient := &JiraClientMock{}

	testCases := []struct {
		title        string
		description string
		expectedErr error
	}{
		{"Atividade 1", "Descrição da atividade 1", nil},
		{"Atividade 2", "", fmt.Errorf("title deve ser não vazios")},
		{"", "Descrição da atividade 3", fmt.Errorf("description deve ser não vazios")},
		{nil, "Descrição da atividade 4", fmt.Errorf("issueID deve ser maior que zero")},
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateIssue(%s, %s)", tc.title, tc.description), func(t *testing.T) {
			err := jiraClient.CreateIssue(tc.title, tc.description)
			if err != nil && err.Error() != tc.expectedErr.Error() {
				t.Errorf("CreateIssue(%s, %s) esperado: %v, obtido: %v", tc.title, tc.description, tc.expectedErr, err)
			}
		})

		t.Run(fmt.Sprintf("UpdateIssue(%d, %s, %s)", 1, tc.title, tc.description), func(t *testing.T) {
			err := jiraClient.UpdateIssue(1, tc.title, tc.description)
			if err != nil && err.Error() != tc.expectedErr.Error() {
				t.Errorf("UpdateIssue(%d, %s, %s) esperado: %v, obtido: %v", 1, tc.title, tc.description, err)
			}
		})
	}
}