package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraAPI
func TestJiraClientCreateIssue(t *testing.T) {
	jira := &JiraAPI{}
	err := jira.CreateIssue("Test Issue", "This is a test issue created by Go Agent and Jira API integration.")
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}

// TestGoAgentClientSendEvent tests the SendEvent method of GoAgentAPI
func TestGoAgentClientSendEvent(t *testing.T) {
	goAgent := &GoAgentAPI{}
	err := goAgent.SendEvent("test_event", map[string]interface{}{
		"event_name":  "test_event",
		"event_data": map[string]string{
			"user": "user123",
		},
	})
	if err != nil {
		t.Errorf("Failed to send event: %v", err)
	}
}