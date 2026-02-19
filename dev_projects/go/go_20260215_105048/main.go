package main

import (
	"fmt"
	"log"

	"github.com/jenkinsci/go-agent/v4/agent"
)

// JiraClient é uma interface para a comunicação com o Jira API
type JiraClient interface {
	CreateIssue(title, description string) error
}

// JiraAPI é um implementação da interface JiraClient usando o RESTful API do Jira
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira para criar um novo issue
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// Main é a função principal que inicializa o Go Agent e faz a integração com o Jira
func main() {
	// Configuração do Go Agent
	config := agent.DefaultConfig()
	config.JenkinsURL = "http://localhost:8080"
	config.JenkinsUsername = "admin"
	config.JenkinsPassword = "password"

	// Inicializa o Go Agent
	agent, err := agent.New(config)
	if err != nil {
		log.Fatalf("Failed to initialize Go Agent: %v", err)
	}

	// Cria um novo issue no Jira usando a API do Jira
	jiraClient := &JiraAPI{}
	err = jiraClient.CreateIssue("Test Issue", "This is a test issue created by the Go Agent.")
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	fmt.Println("Issue created successfully!")
}