package main

import (
	"fmt"
	"log"
)

// JiraClient representa uma interface para interagir com a API do Jira
type JiraClient interface {
	CreateIssue(summary string) error
	UpdateIssue(issueID int, summary string) error
}

// GoAgentClient representa uma interface para interagir com o Go Agent
type GoAgentClient interface {
	SendLog(logMessage string) error
}

// Scrum11Agent implementa a SCRUM-11 - Go Agent
type Scrum11Agent struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

// NewScrum11Agent cria uma nova instância de Scrum11Agent
func NewScrum11Agent(jiraClient JiraClient, goAgentClient GoAgentClient) *Scrum11Agent {
	return &Scrum11Agent{
		jiraClient: jiraClient,
		goAgentClient: goAgentClient,
	}
}

// CreateIssue cria um novo issue no Jira
func (s *Scrum11Agent) CreateIssue(summary string) error {
	log.Println("Creating issue in Jira...")
	return s.jiraClient.CreateIssue(summary)
}

// UpdateIssue atualiza um issue existente no Jira
func (s *Scrum11Agent) UpdateIssue(issueID int, summary string) error {
	log.Println("Updating issue in Jira...")
	return s.jiraClient.UpdateIssue(issueID, summary)
}

// SendLog envia um log para o Go Agent
func (s *Scrum11Agent) SendLog(logMessage string) error {
	log.Println("Sending log to Go Agent...")
	return s.goAgentClient.SendLog(logMessage)
}

// main é a função principal do programa
func main() {
	// Simulação de Jira e Go Agent
	jiraClient := &JiraMock{}
	goAgentClient := &GoAgentMock{}

	agent := NewScrum11Agent(jiraClient, goAgentClient)

	// Criando um novo issue no Jira
	err := agent.CreateIssue("New Scrum 11 Issue")
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	// Atualizando um existing issue no Jira
	err = agent.UpdateIssue(123, "Updated Scrum 11 Issue")
	if err != nil {
		log.Fatalf("Failed to update issue: %v", err)
	}

	// Enviando log para o Go Agent
	err = agent.SendLog("This is a test log from the Go Agent.")
	if err != nil {
		log.Fatalf("Failed to send log: %v", err)
	}
}