import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JiraAgent {

    @Autowired
    private Jira jira;

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private ProjectManager projectManager;

    public void monitorarAtividades() {
        // Implemente aqui a lógica para monitorar atividades em Java
        System.out.println("Iniciando monitoramento de atividades...");
        
        // Exemplo: Listar todas as tarefas do projeto
        String projectId = "10100"; // ID do projeto
        Project project = projectManager.getProjectByKey(projectId);
        if (project != null) {
            System.out.println("Projeto encontrado: " + project.getName());
            
            // Listar todas as tarefas do projeto
            issueManager.getIssuesByProject(project.getId(), false, null, null);
            System.out.println("Tarefas listadas com sucesso.");
        } else {
            System.out.println("Projeto não encontrado.");
        }
    }

    public static void main(String[] args) {
        JiraAgent agent = new JiraAgent();
        agent.monitorarAtividades();
    }
}