from pyVim import connect
from pyVmomi import vim
import json
import atexit

def get_obj(content, vimtype, name=None):
    """Récupère un objet vSphere par son type et nom optionnel."""
    obj = None
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        if name:
            if c.name == name:
                obj = c
                break
        else:
            obj = c
            break
    container.Destroy()
    return obj

def deploy_ova(config_path):
    """Déploie une image OVA en fonction d'un fichier de configuration JSON."""
    
    # Charger la configuration à partir du fichier JSON
    with open(config_path, 'r') as f:
        config = json.load(f)

    esxi_host = config["esxi_host"]
    esxi_user = config["username"]
    esxi_password = config["password"]
    ova_path = config["ova_path"]
    num_instances = config.get("instances", 1)
    network_name = config["network"]
    memory_mb = config["memory_mb"]
    vm_cp = config["vm_cp"]
    datastore_name = config["datastore"]

    # Connexion à l'hôte ESXi sans validation SSL
    context = connect.SmartConnectNoSSL(host=esxi_host, user=esxi_user, pwd=esxi_password)
    atexit.register(connect.Disconnect, context)
    content = context.content

    datacenter = get_obj(content, [vim.Datacenter], "ha-datacenter")  # Remplacez par votre datacenter
    datastore = get_obj(content, [vim.Datastore], datastore_name)
    resource_pool = get_obj(content, [vim.ResourcePool])  # Récupérer le pool de ressources
    network = get_obj(content, [vim.Network], network_name)

    if not datacenter or not datastore or not resource_pool or not network:
        print("Erreur: Datacenter, datastore, pool de ressources ou réseau non trouvé.")
        return

    with open(ova_path, 'r') as ovf_file:
        ovf_descriptor = ovf_file.read()

    ovf_manager = content.ovfManager

    for i in range(num_instances):
        vm_name = f"{config['vm_name']}-{i + 1}"
        import_spec_params = vim.OvfManager.CreateImportSpecParams(entityName=vm_name)
        import_spec = ovf_manager.CreateImportSpec(ovf_descriptor, resource_pool, datastore, import_spec_params)

        if import_spec.error:
            print(f"Erreur lors de la création des spécifications d'importation pour {vm_name}: {import_spec.error}")
            continue

        # Importer le VApp
        task = resource_pool.ImportVApp(import_spec.importSpec, datacenter.vmFolder)
        print(f"Importation de {vm_name} en cours...")

        # Attendre que la tâche soit terminée
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            pass

        if task.info.state == vim.TaskInfo.State.success:
            print(f"{vm_name} importé avec succès.")
        else:
            print(f"Erreur lors de l'importation de {vm_name}: {task.info.error}")

