package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v4"
)

// JiraClient represents a client for interacting with Jira.
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient creates a new JiraClient instance.
func NewJiraClient(jiraURL, username, password string) (*JiraClient, error) {
	config := &jira.Config{
		URL:     jiraURL,
		User:    username,
		Password: password,
	}
	client, err := jira.NewClient(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %v", err)
	}
	return &JiraClient{client}, nil
}

// CreateIssue creates a new issue in Jira.
func (jc *JiraClient) CreateIssue(summary, description string) (*jira.Issue, error) {
	issue := jira.Issue{
		Summary: summary,
		Description: description,
	}
	return jc.client.CreateIssue(&issue)
}

// CloseIssue closes an issue in Jira.
func (jc *JiraClient) CloseIssue(issueKey string) error {
	issue, err := jc.client.GetIssue(issueKey)
	if err != nil {
		return fmt.Errorf("failed to get issue: %v", err)
	}
	issue.Status = jira.Status{
		Name: "Closed",
	}
	return jc.client.UpdateIssue(issueKey, issue)
}

// main is the entry point of the program.
func main() {
	jiraURL := "https://your-jira-instance.atlassian.net"
	username := "your-username"
	password := "your-password"

	client, err := NewJiraClient(jiraURL, username, password)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	issueSummary := "New Feature Request"
	issueDescription := "Implement a new feature in the application."

	newIssue, err := client.CreateIssue(issueSummary, issueDescription)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
	fmt.Printf("Created issue with key: %s\n", newIssue.Key)

	err = client.CloseIssue(newIssue.Key)
	if err != nil {
		log.Fatalf("Failed to close issue: %v", err)
	}
	fmt.Println("Closed the issue.")
}