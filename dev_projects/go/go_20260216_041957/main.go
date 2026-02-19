package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface para a API do Jira
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é uma interface para a API do Go Agent
type GoAgentClient interface {
	TrackActivity(activity string) error
}

// JiraAPI implementa a interface JiraClient
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentAPI implementa a interface GoAgentClient
type GoAgentAPI struct{}

func (g *GoAgentAPI) TrackActivity(activity string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Tracking activity: %s\n", activity)
	return nil
}

// JiraService é uma classe que utiliza o JiraClient para criar issues
type JiraService struct {
	client JiraClient
}

func (js *JiraService) CreateIssue(title, description string) error {
	return js.client.CreateIssue(title, description)
}

// GoAgentService é uma classe que utiliza o GoAgentClient para trackar atividades
type GoAgentService struct {
	client GoAgentClient
}

func (gs *GoAgentService) TrackActivity(activity string) error {
	return gs.client.TrackActivity(activity)
}

// main é a função principal do programa
func main() {
	// Criando instâncias das classes
	jiraClient := &JiraAPI{}
	goAgentClient := &GoAgentAPI{}

	// Criando instâncias das serviços
	jiraService := JiraService{client: jiraClient}
	goAgentService := GoAgentService{client: goAgentClient}

	// Exemplo de uso da serviço
	err := jiraService.CreateIssue("Bug in application", "The application crashes on login")
	if err != nil {
		fmt.Println(err)
		return
	}

	err = goAgentService.TrackActivity("User logged in successfully")
	if err != nil {
		fmt.Println(err)
		return
	}
}