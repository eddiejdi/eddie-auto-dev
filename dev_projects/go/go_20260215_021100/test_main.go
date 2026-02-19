package main

import (
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestJiraIntegrationHandler tests the JiraIntegrationHandler function
func TestJiraIntegrationHandler(t *testing.T) {
	jiraClient := &Jira{}
	goAgentClient := &GoAgent{}

	testCases := []struct {
		title         string
		description    string
		expectedStatus int
	}{
		{"Test Issue", "This is a test issue", http.StatusOK},
		{"Invalid Title", "", http.StatusBadRequest},
		{"Empty Description", " ", http.StatusBadRequest},
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateIssue(%s, %s)", tc.title, tc.description), func(t *testing.T) {
			req := &http.Request{
				Method:  "POST",
				URL:    "/jira-integration",
				Body:   strings.NewReader(fmt.Sprintf("title=%s&description=%s", tc.title, tc.description)),
				Header: http.Header{},
			}

			w := httptest.NewRecorder()
			JiraIntegrationHandler(w, req)

			assert.Equal(t, tc.expectedStatus, w.Code)
		})
	}
}