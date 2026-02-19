package main_test

import (
	"testing"
)

// Teste para criar um novo issue no Jira
func TestCreateIssue(t *testing.T) {
	jira := JiraAPI{}
	jiraGoa := JiraJiraClient{jira: jira, goa: GoAgentAPI{}}

	err := jiraGoa.CreateIssue("Test Issue", "This is a test issue created by Go Agent and Jira.")
	if err != nil {
		t.Errorf("Error creating issue: %v", err)
	}
}

// Teste para enviar um evento para o Go Agent
func TestSendEvent(t *testing.T) {
	jira := JiraAPI{}
	goa := GoAgentAPI{}

	jiraGoa := JiraJiraClient{jira: jira, goa: goa}

	eventData := map[string]interface{}{
		"event":   "test",
		"data":    "Hello, World!",
		"timeStamp": 1633072800,
	}
	err := jiraGoa.SendEvent("Test Event", eventData)
	if err != nil {
		t.Errorf("Error sending event: %v", err)
	}
}

// Teste para criar um novo issue com valores inválidos
func TestCreateIssueInvalidValues(t *testing.T) {
	jira := JiraAPI{}
	jiraGoa := JiraJiraClient{jira: jira, goa: GoAgentAPI{}}

	err := jiraGoa.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected error creating issue with empty values")
	}
}

// Teste para enviar um evento com valores inválidos
func TestSendEventInvalidValues(t *testing.T) {
	jira := JiraAPI{}
	goa := GoAgentAPI{}

	jiraGoa := JiraJiraClient{jira: jira, goa: goa}

	eventData := map[string]interface{}{
		"event":   "",
		"data":    "",
		"timeStamp": "",
	}
	err := jiraGoa.SendEvent("", eventData)
	if err == nil {
		t.Errorf("Expected error sending event with empty values")
	}
}