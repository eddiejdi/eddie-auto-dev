package main

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/stretchr/testify/assert"
)

// TestJiraAPICreateIssue tests the CreateIssue method of JiraAPI
func TestJiraAPICreateIssue(t *testing.T) {
	jira := &JiraAPI{
		URL: "https://your-jira-instance.atlassian.net",
	}

	tests := []struct {
		title        string
		description string
		expected    error
	}{
		{"New Feature", "Implement a new feature in the application", nil},
		{"Invalid Title", "", fmt.Errorf("title cannot be empty")},
		{"Empty Description", "Implement a new feature in the application", fmt.Errorf("description cannot be empty")},
	}

	for _, tt := range tests {
		t.Run(fmt.Sprintf("CreateIssue(%s, %s)", tt.title, tt.description), func(t *testing.T) {
			err := jira.CreateIssue(tt.title, tt.description)
			assert.Equal(t, tt.expected, err)
		})
	}
}