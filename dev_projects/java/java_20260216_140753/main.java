import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.user.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class JavaAgent {

    @Autowired
    private Jira jira;

    public void monitorarAtividades() {
        try {
            // Obter a lista de projetos
            Project[] projects = jira.getProjects();

            for (Project project : projects) {
                System.out.println("Projeto: " + project.getName());

                // Obter a lista de usuários do projeto
                User[] users = jira.getProjectUsers(project.getKey());

                for (User user : users) {
                    System.out.println("Usuário: " + user.getDisplayName());
                }

                // Monitorar atividades do usuário
                monitorarAtividade(user);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void monitorarAtividade(User user) {
        try {
            // Obter a lista de issues do usuário
            Issue[] issues = jira.getUserIssues(user.getKey());

            for (Issue issue : issues) {
                System.out.println("Issue: " + issue.getKey() + " - Status: " + issue.getStatus().getName());
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JavaAgent javaAgent = new JavaAgent();

        try {
            javaAgent.monitorarAtividades();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}