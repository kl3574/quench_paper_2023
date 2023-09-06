import numpy as np
import os
import glob
from quench_library import angle_distance2_pbc,log_sum

# load parameters
import yaml,sys
if len(sys.argv) != 2 or sys.argv[1][-5:] != ".yaml":
    print("Usage %s yaml_file"%(sys.argv[0]))
    sys.exit(-1)
with open(sys.argv[1],'r') as f:
    parameters = yaml.full_load(f)
    high_T_params = parameters["high_T"]
    umbrella_params = parameters["umbrella"]
    analysis_params = parameters["analysis"]
    globals().update(high_T_params)
    globals().update(umbrella_params)
    globals().update(analysis_params)
dpsi = 2.0 * np.pi / psi_windows
psi_centers = np.arange(-np.pi+dpsi/2.0,np.pi,dpsi)
fes_dphi = 2.0 * np.pi / fes_phi_windows
fes_dpsi = 2.0 * np.pi / fes_psi_windows
fes_phi_centers = np.arange(-np.pi+fes_dphi/2.0,np.pi,fes_dphi)
fes_psi_centers = np.arange(-np.pi+fes_dpsi/2.0,np.pi,fes_dpsi)

run_kbt = run_temp * kb
in_dir_prefix = os.path.join(os.getcwd(),"analysis","T%.1f"%(run_temp))
out_dir = os.path.join(os.getcwd(),"wham_analysis","T%.1f"%(run_temp),"rho%d_k%.1f"%(psi_windows,kappa))
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

for target_temp in target_temp_list:
    target_kbt = target_temp * kb
    # generate w_ij_kl
    w_file = os.path.join(out_dir,"w_%dx%d_%d_k%.1f.npy"%(psi_windows,fes_phi_windows,fes_psi_windows,kappa))
    if not os.path.exists(w_file):
        w_ij_kl = np.zeros((psi_windows,fes_phi_windows,fes_psi_windows))
        for j,psi in enumerate(psi_centers):
            for l,fes_psi in enumerate(fes_psi_centers):
                psi_distance2 = angle_distance2_pbc(psi,fes_psi)
                for k,fes_phi in enumerate(fes_phi_centers):
                    w_ij_kl[j,k,l] = 0.5 * kappa * psi_distance2
        np.save(os.path.join(out_dir,"w_%d_%dx%d_k%.1f.npy"%(psi_windows,fes_phi_windows,fes_psi_windows,kappa)),w_ij_kl)
        print("shape",w_ij_kl.shape)
    
    for quench_gamma in quench_gamma_list:
        for num_restart in num_restart_list:
            # generate rho_ij_kl
            rho_file = os.path.join(out_dir,"infinite_stopping_rho_%d_%dx%d_k%.1f_tt%.1f_qg%.2e_N%d.npy"%(psi_windows,fes_phi_windows,fes_psi_windows,kappa,target_temp,quench_gamma,num_restart))
            if not os.path.exists(rho_file):
                rho_ij_kl = np.zeros((psi_windows,fes_phi_windows,fes_psi_windows))
                for j,psi in enumerate(psi_centers):
                    in_dir = os.path.join(in_dir_prefix,"psi%.2f_k%.1f"%(psi,kappa))
                    lnrho_ij_list = np.load(os.path.join(in_dir,"infinite_stopping_lnrho_list_psi%.2f_k%.1f_qg%.2e_tt%.1f_%dx%d.npy"%(psi,kappa,quench_gamma,target_temp,fes_phi_windows,fes_psi_windows)))
                    lnrho_ij_list = lnrho_ij_list[:num_restart,:,:]
                    lnrho_ij = np.ones((fes_phi_windows,fes_psi_windows)) * -np.inf
                    for k in range(fes_phi_windows):
                        for l in range(fes_psi_windows):
                            lnrho_ij[k,l] = log_sum(lnrho_ij_list[:,k,l])
                    lnQ_ij_list = np.load(os.path.join(in_dir,"infinite_stopping_lnQ_list_psi%.2f_k%.1f_qg%.2e_tt%.1f_%dx%d.npy"%(psi,kappa,quench_gamma,target_temp,fes_phi_windows,fes_psi_windows)))
                    lnQ_ij_list = lnQ_ij_list[:num_restart]
                    lnrho_ij -= log_sum(lnQ_ij_list)
                    rho_ij_kl[j,:,:] = np.exp(lnrho_ij)
                np.save(os.path.join(out_dir,"infinite_stopping_rho_%d_%dx%d_k%.1f_tt%.1f_qg%.2e_N%d.npy"%(psi_windows,fes_phi_windows,fes_psi_windows,kappa,target_temp,quench_gamma,num_restart)),rho_ij_kl)
                print("shape",rho_ij_kl.shape)
            
            # initialize
            rho_ij_kl = np.load(os.path.join(out_dir,"infinite_stopping_rho_%d_%dx%d_k%.1f_tt%.1f_qg%.2e_N%d.npy"%(psi_windows,fes_phi_windows,fes_psi_windows,kappa,target_temp,quench_gamma,num_restart)))
            w_ij_kl = np.load(os.path.join(out_dir,"w_%d_%dx%d_k%.1f.npy"%(psi_windows,fes_phi_windows,fes_psi_windows,kappa)))
            print("rho_ij_kl:",rho_ij_kl)
            print("w_ij_kl:",w_ij_kl)
            N_ij = np.sum(rho_ij_kl,axis=(-2,-1))
            N_kl = np.sum(rho_ij_kl,axis=(0))
            print("N_ij:",N_ij)
            print("N_kl:",N_kl)
            rho_kl = np.ones((fes_phi_windows,fes_psi_windows))
            F_kl = -target_kbt * np.log(rho_kl)
            F_kl -= F_kl.min()
            c_ij_inverse = np.zeros((psi_windows))
            for j in range(psi_windows):
                c_ij_inverse[j] = np.sum(rho_kl * np.exp(-w_ij_kl[j,:,:]/target_kbt))
            
            # WHAM equations
            step = 0
            error = 1.0
            while(error > tolerance):
                step += 1
                old_rho_kl = rho_kl.copy()
                old_F_kl = F_kl.copy()
                old_c_ij_inverse = c_ij_inverse.copy()
                # update rho_kl,F_kl, minimize F_kl to 0
                for k in range(fes_phi_windows):
                    for l in range(fes_psi_windows):
                        rho_kl[k,l] = N_kl[k,l] / np.sum(N_ij * np.exp(-w_ij_kl[:,k,l]/target_kbt) / old_c_ij_inverse)
                mask = rho_kl != 0.
                old_mask = old_rho_kl != 0.
                F_kl = -target_kbt * np.log(rho_kl)
                F_kl -= F_kl.min()
                # update c_ij_inverse
                for j in range(psi_windows):
                    c_ij_inverse[j] = np.sum(rho_kl * np.exp(-w_ij_kl[j,:,:]/target_kbt))
                # compute error of F_kl (largest)
                total_mask = np.logical_and(mask,old_mask)
                error = np.abs(F_kl[total_mask] - old_F_kl[total_mask]).max()
                print("Step %d, error = %f"%(step,error))
            
            # save results
            np.save(os.path.join(out_dir,"infinite_stopping_psi_rho_%dx%d_k%.1f_rt%.1f_tt%.1f_qg%.2e_N%d.npy"%(fes_phi_windows,fes_psi_windows,kappa,run_temp,target_temp,quench_gamma,num_restart)),rho_kl)
            np.save(os.path.join(out_dir,"infinite_stopping_psi_F_%dx%d_k%.1f_rt%.1f_tt%.1f_qg%.2e_N%d.npy"%(fes_phi_windows,fes_psi_windows,kappa,run_temp,target_temp,quench_gamma,num_restart)),F_kl)
            
