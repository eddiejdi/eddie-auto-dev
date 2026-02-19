package main_test

import (
	"testing"
)

// TestTrackActivity tests the TrackActivity method of GoAgent.
func TestTrackActivity(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := GoAgent{jiraClient}

	testCases := []struct {
		name     string
		title    string
		description string
		expected error
	}{
		{
			name:     "Success with valid inputs",
			title:    "New Feature Request",
			description: "Implement a new feature in the application.",
			expected: nil,
		},
		{
			name:     "Error creating issue",
			title:    "Invalid Title",
			description: "Implement a new feature in the application.",
			expected: fmt.Errorf("Error tracking activity"),
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := goAgent.TrackActivity(tc.title, tc.description)
			if err != tc.expected {
				t.Errorf("TrackActivity(%s, %s) = %v; want %v", tc.title, tc.description, err, tc.expected)
			}
		})
	}
}

// MockJiraClient is a mock implementation of JiraClient.
type MockJiraClient struct{}

// CreateIssue creates an issue in Jira.
func (m *MockJiraClient) CreateIssue(title, description string) error {
	if title == "" || description == "" {
		return fmt.Errorf("Invalid input: Title and Description cannot be empty")
	}
	return nil
}