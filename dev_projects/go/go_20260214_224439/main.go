package main

import (
	"fmt"
	"log"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct {
	url    string
	token  string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url, token string) *JiraClient {
	return &JiraClient{
		url: url,
		token: token,
	}
}

// CreateIssue cria um novo issue no Jira
func (j *JiraClient) CreateIssue(summary, description string) error {
	// Simulação de requisição HTTP para criar um issue
	fmt.Printf("Creating issue with summary: %s and description: %s\n", summary, description)
	return nil
}

// UpdateIssue atualiza um existing issue no Jira
func (j *JiraClient) UpdateIssue(issueID int, summary, description string) error {
	// Simulação de requisição HTTP para atualizar um issue
	fmt.Printf("Updating issue %d with summary: %s and description: %s\n", issueID, summary, description)
	return nil
}

func main() {
	jiraClient := NewJiraClient("https://your-jira-url.com/rest/api/2/", "your-jira-token")

	// Criando um novo issue
	err := jiraClient.CreateIssue("Bug in Go Agent", "Go Agent is not working as expected")
	if err != nil {
		log.Fatalf("Error creating issue: %v\n", err)
	}

	// Atualizando um existing issue
	err = jiraClient.UpdateIssue(123, "Bug in Go Agent", "Go Agent is now working properly")
	if err != nil {
		log.Fatalf("Error updating issue: %v\n", err)
	}
}