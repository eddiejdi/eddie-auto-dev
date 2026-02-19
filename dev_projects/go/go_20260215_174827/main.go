package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface para a API do Jira
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é uma interface para o Go Agent
type GoAgentClient interface {
	TrackActivity(activityName string) error
}

// JiraAdapter implementa a interface JiraClient usando a API do Jira
type JiraAdapter struct{}

func (ja JiraAdapter) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira para criar um novo issue
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// GoAgentAdapter implementa a interface GoAgentClient usando o Go Agent
type GoAgentAdapter struct{}

func (ga GoAgentAdapter) TrackActivity(activityName string) error {
	// Simulação de chamada ao Go Agent para marcar uma atividade
	fmt.Printf("Tracking activity '%s'\n", activityName)
	return nil
}

// JiraService é um serviço que utiliza o JiraClient para criar issues
type JiraService struct {
	client JiraClient
}

func (js *JiraService) CreateIssue(title, description string) error {
	return js.client.CreateIssue(title, description)
}

// GoAgentService é um serviço que utiliza o GoAgentClient para marcar atividades
type GoAgentService struct {
	client GoAgentClient
}

func (gs *GoAgentService) TrackActivity(activityName string) error {
	return gs.client.TrackActivity(activityName)
}

// main é a função principal do programa
func main() {
	// Criando instâncias de JiraAdapter e GoAgentAdapter
	jira := &JiraAdapter{}
	goAgent := &GoAgentAdapter{}

	// Criando serviços para cada cliente
	jiraService := &JiraService{client: jira}
	goAgentService := &GoAgentService{client: goAgent}

	// Exemplo de uso dos serviços
	err := jiraService.CreateIssue("Bug in Go Agent", "The Go Agent is not working as expected.")
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}

	err = goAgentService.TrackActivity("Go Agent activity")
	if err != nil {
		fmt.Println("Error tracking activity:", err)
		return
	}
}