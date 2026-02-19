package main

import (
	"fmt"
	"log"
	"net/http"
)

// JiraClient é a interface para interagir com Jira
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é a interface para interagir com Go Agent
type GoAgentClient interface {
	SendAlert(message string) error
}

// Scrum11Integrator é a classe que realiza o trabalho de integrar Go Agent com Jira
type Scrum11Integrator struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

// NewScrum11Integrator cria uma nova instância do Integrator
func NewScrum11Integrator(jiraClient, goAgentClient JiraClient) *Scrum11Integrator {
	return &Scrum11Integrator{
		jiraClient: jiraClient,
		goAgentClient: goAgentClient,
	}
}

// CreateIssue cria um novo issue no Jira
func (i *Scrum11Integrator) CreateIssue(title, description string) error {
	log.Printf("Creating issue in Jira: %s", title)
	return i.jiraClient.CreateIssue(title, description)
}

// SendAlert envia uma alerta para Go Agent
func (i *Scrum11Integrator) SendAlert(message string) error {
	log.Printf("Sending alert to Go Agent: %s", message)
	return i.goAgentClient.SendAlert(message)
}

// main é a função principal do programa
func main() {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	integrator := NewScrum11Integrator(jiraClient, goAgentClient)

	// Simulando uma nova atividade
	title := "New Task"
	description := "Implement Go Agent integration with Jira"

	err := integrator.CreateIssue(title, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	// Simulando um evento de alerta
	message := "Go Agent is down!"
	err = integrator.SendAlert(message)
	if err != nil {
		log.Fatalf("Failed to send alert: %v", err)
	}
}