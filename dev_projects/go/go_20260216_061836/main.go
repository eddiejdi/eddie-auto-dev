package main

import (
	"fmt"
	"log"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgent integrado com Jira
type GoAgent struct {
	jiraClient JiraClient
}

// NewGoAgent cria uma nova instância de GoAgent
func NewGoAgent(jiraClient JiraClient) *GoAgent {
	return &GoAgent{jiraClient: jiraClient}
}

// CreateIssue cria um novo issue no Jira
func (g *GoAgent) CreateIssue(title string, description string) error {
	// Simulação da chamada ao Jira API para criar um novo issue
	fmt.Printf("Creating issue '%s' with description '%s'\n", title, description)
	return nil
}

func main() {
	// Cria uma instância do JiraClient usando a implementação local
	jiraClient := &LocalJiraClient{}

	// Cria uma nova instância de GoAgent com o JiraClient
	goAgent := NewGoAgent(jiraClient)

	// Cria um novo issue no Jira
	err := goAgent.CreateIssue("New Test Issue", "This is a test issue created by Go Agent")
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
}