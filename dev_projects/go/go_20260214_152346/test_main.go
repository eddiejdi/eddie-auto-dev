package main

import (
	"testing"
)

// TestJiraClientStart tests the Start method of JiraClient.
func TestJiraClientStart(t *testing.T) {
	jira := &JiraClient{}
	err := jira.Start()
	if err != nil {
		t.Errorf("Start method failed: %v", err)
	}
}

// TestJiraClientStop tests the Stop method of JiraClient.
func TestJiraClientStop(t *testing.T) {
	jira := &JiraClient{}
	err := jira.Stop()
	if err != nil {
		t.Errorf("Stop method failed: %v", err)
	}
}