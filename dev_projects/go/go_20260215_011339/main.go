package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v5"
)

// JiraClient é a estrutura que representa o cliente para interagir com o Jira.
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient cria um novo cliente para interagir com o Jira usando as credenciais fornecidas.
func NewJiraClient(username, password string) (*JiraClient, error) {
	jiraConfig := &jira.Config{
		Server:     "https://your-jira-server.com",
		Username: username,
		Password: password,
	}

	client, err := jira.New(jiraConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %w", err)
	}

	return &JiraClient{client: client}, nil
}

// CreateIssue cria um novo issue no Jira.
func (jc *JiraClient) CreateIssue(title, description string) (*jira.Issue, error) {
	issue := &jira.Issue{
		Title:     title,
		Description: description,
		Type: jira.IssueType{
			Name: "Bug",
		},
	}

	newIssue, err := jc.client.CreateIssue(issue)
	if err != nil {
		return nil, fmt.Errorf("failed to create issue: %w", err)
	}

	fmt.Printf("Created issue with ID: %s\n", newIssue.ID)
	return newIssue, nil
}

// main é a função principal que executa o código.
func main() {
	username := "your-jira-username"
	password := "your-jira-password"

	jc, err := NewJiraClient(username, password)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	title := "New Feature Request"
	description := "Implement a new feature in the application."

	newIssue, err := jc.CreateIssue(title, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
}