package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v4"
)

// JiraClient representa a conexão com o Jira
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url, token string) (*JiraClient, error) {
	config := jira.Config{
		URL:     url,
		Token:  token,
	}

	jiraClient, err := jira.New(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %v", err)
	}
	return &JiraClient{jiraClient}, nil
}

// CreateIssue cria um novo issue no Jira
func (jc *JiraClient) CreateIssue(summary string, description string) (*jira.Issue, error) {
	fields := jira.Fields{
		Title:       summary,
		Description: description,
	}
	return jc.client.CreateIssue(fields)
}

// UpdateIssue atualiza um existing issue no Jira
func (jc *JiraClient) UpdateIssue(issueID int, fields map[string]interface{}) (*jira.Issue, error) {
	return jc.client.UpdateIssue(issueID, fields)
}

// DeleteIssue deleta um existing issue no Jira
func (jc *JiraClient) DeleteIssue(issueID int) error {
	return jc.client.DeleteIssue(issueID)
}

func main() {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	summary := "New Test Case"
	description := "This is a new test case for the Go Agent integration."

	newIssue, err := jiraClient.CreateIssue(summary, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
	fmt.Printf("Created issue with ID: %d\n", newIssue.ID)

	// Update the issue
	fieldsToUpdate := map[string]interface{}{
		"status": "In Progress",
	}
	err = jiraClient.UpdateIssue(newIssue.ID, fieldsToUpdate)
	if err != nil {
		log.Fatalf("Failed to update issue: %v", err)
	}

	fmt.Printf("Updated issue with ID: %d\n", newIssue.ID)

	// Delete the issue
	err = jiraClient.DeleteIssue(newIssue.ID)
	if err != nil {
		log.Fatalf("Failed to delete issue: %v", err)
	}
	fmt.Printf("Deleted issue with ID: %d\n", newIssue.ID)
}